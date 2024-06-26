# pylint: disable=import-error
# pylint: disable=missing-function-docstring
# pylint: disable=fixme
# pylint: disable=missing-module-docstring
# pylint: disable=consider-using-with
# pylint: disable=consider-using-f-string
# pylint: disable=unspecified-encoding

# This file has been copied from
# https://github.com/aspect-build/bazel-examples/blob/main/oci_python_image/hello_world/app_test.py
# and adjusted to work with the repo_structure repository
import io
import json
import os
import tarfile
import tempfile

import docker

# Loads individual layers from disk by reading their blob locations from
# the OCI format JSON descriptor file.
# TODO: upstream some of this to the testcontainers library to simplify similar code for users.
from testcontainers.core.container import DockerContainer
from testcontainers.core.waiting_utils import wait_for_logs


def add_json_file(tar, name, contents):
    content = json.dumps(contents).encode("utf-8")
    info = tarfile.TarInfo(name=name)
    info.size = len(content)
    tar.addfile(info, fileobj=io.BytesIO(content))


def add_file(tar, name, fileobj):
    info = tarfile.TarInfo(name=name)
    info.size = os.fstat(fileobj.fileno()).st_size
    tar.addfile(info, fileobj=fileobj)
    fileobj.close()


def get_blob_path(image, digest):
    return "%s/blobs/%s" % (image, digest.replace(":", "/"))


def open_blob(image, digest):
    return open(get_blob_path(image, digest), "rb")


def oci_image_container(image):
    with open("%s/index.json" % image) as indexp:
        indexjson = json.load(indexp)

    with open_blob(image, indexjson["manifests"][0]["digest"]) as manifestp:
        manifest = json.load(manifestp)

    with open_blob(image, manifest["config"]["digest"]) as configp:
        config = json.load(configp)

    client = docker.from_env()

    # Probe and layer loading phase
    layers = manifest["layers"]
    needed = []
    i = 0
    while i < len(layers):
        layer = layers[i]
        tmp = tempfile.NamedTemporaryFile(suffix=".tar")
        tar = tarfile.open(fileobj=tmp, mode="w")

        add_json_file(
            tar,
            name="manifest.json",
            contents=[
                {
                    "Config": "config.json",
                    "RepoTags": [],
                    "Layers": list(
                        map(lambda x: x["digest"], manifest["layers"][: i + 1])
                    ),
                }
            ],
        )
        add_json_file(
            tar,
            name="config.json",
            contents={
                "rootfs": {
                    "type": "layers",
                    "diff_ids": config["rootfs"]["diff_ids"][: i + 1],
                }
            },
        )

        if layer["digest"] in needed:
            add_file(
                tar, name=layer["digest"], fileobj=open_blob(image, layer["digest"])
            )

        tar.close()

        try:
            r = client.images.load(open(tmp.name, "rb"))
            i += 1
            # print(r[0].id)
            # os.system("tar -tvf %s" % tmp.name)
        except docker.errors.ImageLoadError:
            needed.append(layer["digest"])

    # Config loading phase
    tmp = tempfile.NamedTemporaryFile(suffix=".tar")
    tar = tarfile.open(fileobj=tmp, mode="w")
    add_json_file(
        tar,
        name="manifest.json",
        contents=[
            {
                "Config": "config.json",
                "RepoTags": [],
                "Layers": list(map(lambda x: x["digest"], manifest["layers"])),
            }
        ],
    )
    add_file(
        tar, name="config.json", fileobj=open_blob(image, manifest["config"]["digest"])
    )
    tar.close()
    r = client.images.load(open(tmp.name, "rb"))
    return DockerContainer(r[0].id)


def test_wait_for_hello():
    with oci_image_container("image") as container:
        wait_for_logs(container, "Usage: ", timeout=2)


test_wait_for_hello()

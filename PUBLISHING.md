# Creating a New Release

Simple check list to go through for creating a new release

- [ ] Create PR with updated version strings with new version string, e.g.
      search and replace all occurrences of "0.4.4" (without v prefix!)
- [ ] Do NOT change the consumption in `.pre-commit-config.yaml` just yet
- [ ] Merge that PR
- [ ] Create new release on GitHub (with the new tag)
- [ ] Create and land a PR with updated version in `.pre-commit.config.yaml`

Important to note is that the time between merging the PR with the new release
version and the creation of the new release should be minimal.

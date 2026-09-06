# Internal changes:

## Release notes no longer hard-wrapped:
- `release-on-merge.yml` sourced the GitHub Release body from the merge commit's own message
  (`git log -1 --format=%b`), which GitHub's squash-merge textarea hard-wraps at ~72 characters
  when composing the merge commit. Fixed to read `github.event.pull_request.body` directly from
  the `pull_request: closed` event payload instead, since the plain PR description field doesn't
  get wrapped the same way regardless of merge strategy used.

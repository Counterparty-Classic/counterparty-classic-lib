**Development team:**

- Merge pending dev branches into `develop`
- Update `ChangeLog.md`
- Update `VERSION_` variables in `lib/config.py`
- Update `protocol_changes.json` (as necessary)
- Create `develop` PR to merge into `master` for final dev team review
- Make sure all PR CI test runners pass
- Merge PR into `master`
- Tag and Sign Release (for release notes, use the relevant text from `ChangeLog.md`)
- Update documentation (as appropriate)
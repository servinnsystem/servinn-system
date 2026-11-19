# SERVINN workflow trial

Backup: backups/workflow-20261006-130419. manifest.json lists the previous files; changes.json identifies changed/new files. Restore only changed files from the backup and remove only the listed added files to undo this trial. Compare against later edits before restoring. No live database changes were made during implementation.

Implemented: private document resubmission with file size/signature/extension checks; administrator feedback and clearance downloads; Verified/Approved required to apply; explainable skill/location/employment preference ranking; Reviewed, Shortlisted, Interview Invitation, Accepted, Rejected and Hired stages; interview date/location and candidate message; decision history; application notifications; employer close/archive/reopen and admin posting moderation.

Try: submit documents as a seeker, review them in the administrator account, browse ranked jobs and apply. As the job owner, mark Reviewed, Shortlisted, schedule a future interview, Accept, then Hired. Open My applications to inspect the message, interview and history. Close/archive a job and confirm it disappears from search.

Limits: notifications are polled every five seconds while a page is open, not background push or SMS. The feed contains the latest decision; full decision history is in My applications. Reload/open an application to refresh counters/details. Ranking is a transparent heuristic, not AI or an eligibility guarantee. File checks do not establish identity or document authenticity; an administrator makes that decision. Archive preserves application records rather than permanently deleting data. Existing authentication, Firebase storage and security configuration remain in use; this trial does not add disaster recovery or certify encryption/security compliance.

Rollback restores code/UI, not user actions performed during the trial. Uploaded files, review decisions, interview details and archived postings created during testing remain in storage and must be reviewed separately. Old applications need a new status decision to acquire a notification timestamp/history; history is not fabricated for previous decisions.

# Job publication workflow

1. An employer signs in and completes their profile before opening the job submission form.
2. A valid submission is saved with `status: Pending Review` and `review_status: Pending`. It is hidden from job seekers.
3. An authenticated administrator opens Administration > Manage job postings and reads the employer account, job description, skills, location, employment type, salary and experience requirements.
4. The administrator chooses Approve & publish, Request corrections, or Reject. Corrections and rejections require feedback. Decisions record the administrator and review time; approvals record the publication time.
5. Employers see their posting status and review feedback on their dashboard. Every content edit submits the posting for a new review and immediately hides it until approval.
6. Employers may close or archive their postings. They may reactivate only postings whose current content has already been approved.

Only jobs with both `status: Active` and `review_status: Approved` are available in public search, recommendations, the job seeker dashboard, direct detail links, saving, applications and ratings. Existing postings without an explicit approval are hidden until an administrator reviews them. Existing applications are retained.

The review form includes the Firestore document version. A changed posting cannot be approved from an outdated review page, and version preconditions protect concurrent writes. No database migration or automatic approval of existing postings is performed.

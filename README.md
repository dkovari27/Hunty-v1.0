How to run Hunty:
Go to the Actions tab at the top of the repo page
In the left sidebar, click Hunty Job Scraper (the workflow name)
On the right side, click the Run workflow dropdown button
Leave the branch as main, click the green Run workflow button
Refresh the page — a new run appears at the top with a yellow spinner; click it to watch the logs live



Schedule and modes:
The workflow runs automatically Monday and Thursday at 08:00 UTC (09:00 CET / 10:00 CEST). GitHub does not guarantee an exact start time for scheduled workflows, actual starts can run late (sometimes by several hours) under GitHub-wide load; this is a platform limit, not something the workflow controls.

Three modes exist (pick one from the Run workflow dropdown for a manual run; the scheduled run always uses "switzerland"):
- switzerland (scheduled default): LinkedIn only, scoped to Switzerland. jobs.ch, organic-chemistry.org, Swiss company career pages, the European multi-country boards, and Exa are all off. Fast.
- switzerland-weekly (manual only): LinkedIn, jobs.ch, and organic-chemistry.org, plus Swiss company career pages, with a 1.5-week lookback window. Slow (~1.5 h).
- eu (manual only): full 14-country EU search, including the European multi-country boards. Very slow (~4 h).

Keywords and the prefilter (required/excluded terms, excluded locations) are read from settings/last_used.json, which the desktop GUI autosaves and commits to git, so whatever is configured in the GUI is what the scheduled run uses.


How to get the perfect keyword filtering of your CV that can be easily pasted into Hunty:
Copy the following text into any AI and add your CV to the message.

I'm going to paste my CV below. Extract the information needed to configure a job search tool called Hunty. Return exactly five sections, formatted as Python lists/strings ready to paste into a config file.

1. SEARCH_KEYWORDS — 6–10 multi-word search phrases optimised for LinkedIn and semantic search (e.g. "Senior mechanical engineer automotive"). Each phrase should combine a role title with a key skill or sector.

2. SWISS_SEARCH_KEYWORDS — 4–6 short single- or two-word terms for Swiss job boards like jobs.ch (e.g. "Mechanical Engineer", "CAD design"). These must be short — long phrases don't work on Swiss boards.

3. JOB_PROFILE — A structured plain-text paragraph summarising: current role, previous roles, education, core skills, target roles, target sectors, preferred location, languages, and anything the candidate is NOT interested in. Be specific and honest.

4. PREFILTER_REQUIRED — 8–15 lowercase substrings. Any job whose title AND description contains none of these is dropped before AI scoring. Choose root substrings that cover the relevant field (e.g. "mech", "engineer", "cad", "design").

5. PREFILTER_EXCLUDED_TITLE — 15–25 lowercase phrases. Any job whose title contains any of these is dropped immediately. Include unrelated professions, wrong seniority levels, academic roles, and disciplines that sound adjacent but aren't relevant.

Format the output as valid Python — I will paste it directly into config_personal.py.

Here is my CV:
[PASTE CV TEXT HERE]

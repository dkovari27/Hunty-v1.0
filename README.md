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

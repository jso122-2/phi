# Celeste scribble

#keep #imported

> created_ts: 2024-08-27-133515  
> Created: 2024-08-27 13:35 UTC  
> Edited: 2024-09-04 09:30 UTC  
> Source: Google Keep  

---

summaries 27/8/34

Goal: Develop a filter for targeted marketing using Spotify data from a musician's personal data request to build Instagram ads, leveraging affinity rankings.
Timeline: Originally planned for two weeks, now stretched to a week and a half.
Plan Breakdown:
Week 1: Focus on understanding and organizing data, defining audience segments, and researching targeting strategies.
Week 2: Implement filter criteria, set up the Instagram ad infrastructure, create ads, and run initial tests.
Estimated Hours: Total time commitment of about 36-46 hours, spread across the tasks.

summaries 1/09/24

1. Access Token Validation and Issue Troubleshooting
We started by confirming that your Spotify API access token was valid. After encountering a 401 Unauthorized error when trying to fetch playlist data, we regenerated the access token and verified its functionality using a test script. The access token was confirmed to be working correctly when used to retrieve basic artist information for "C ME."
2. Playlist Data Collection
We attempted to gather detailed data on editorial playlists that might contain tracks by "C ME." Initial attempts to retrieve this data were unsuccessful, leading us to troubleshoot the issue further. We suspected that the lack of data might be due to the playlists not containing any tracks by "C ME," or issues related to how the Spotify API handles searches and playlist data retrieval.
3. Refinement of Data Collection Approach
To address the issue of no data being returned, we tried a different approach: searching for tracks by "C ME" across Spotify, then identifying which playlists contain these tracks. This method was intended to ensure that we were targeting playlists that actually feature "C ME" tracks, increasing the likelihood of collecting relevant data. However, this attempt also did not yield data, suggesting a need for further refinement or different strategies for data collection.
4. Planning for Next Steps
As we continued troubleshooting, we explored options such as refining the search queries, validating playlist IDs, and considering different data collection methods. The focus remained on ensuring that we could gather comprehensive data on "C ME" tracks within Spotify’s editorial playlists, which would be crucial for targeted marketing and audience segmentation efforts.
Throughout these efforts, we iteratively tested scripts and adjusted our approach based on the results. Although we encountered challenges in collecting the desired data, we made significant progress in identifying the potential issues and setting the stage for a more targeted data collection strategy moving forward.

Let me know when you're back, and we can continue refining the approach to gather the necessary data!

summaries 4/9/24

Here’s a summary of what we accomplished in the last 4 hours:

Data Gathering and Processing:

We focused on retrieving and processing multiple datasets related to the artist 'C ME', including demographic, engagement, top tracks, and related artist data.
We encountered and resolved various issues around data extraction, such as parsing issues and file format problems.
We specifically worked on cleaning data from various playlists and related artist metrics, consolidating this information into well-structured CSV files.
Lookalike Audience Creation:

We moved on to segmenting the audience data based on factors such as popularity and follower count for related artists.
This segmentation created three main groups (high, medium, and low engagement), using clustering techniques.
You successfully generated the lookalike audience data and saved it into appropriate CSV files, ready for integration into advertising platforms.
Ad Campaign Strategy:

We discussed a clear approach for setting up Facebook/Instagram ad campaigns based on the lookalike audience segments.
Instructions were provided on how to upload the audience data, create custom audiences, and potentially use Facebook’s Lookalike Audience feature for wider reach.
A step-by-step guide was laid out for setting up separate ad sets targeting high, medium, and low engagement audiences.
Next Steps:

After successfully generating the audience segmentation and lookalike data, the next step is to upload this to Facebook/Instagram Ads Manager to begin setting up campaigns.
You'll also need to monitor the campaign performance once they are live, to optimize budgets and targeting strategies.
This session involved a lot of work on data cleaning, audience segmentation, and preparation for targeted marketing. You’re all set to start running campaigns next! Let me know when you're ready to continue.

---

## Semantic links

→ [[2026-07-13-042743-configure-the-obsidian-graph-as-the-hub-buil]]

## Related notes

→ [[keep/2024-08-27-135521-cme-marketing-timeline]]
→ [[keep/2025-02-13-054731-13-2-25-scribble]]
→ [[keep/2026-01-30-154734-2026-01-31t02-47-34-664-11-00]]
→ [[keep/2026-04-30-131517-dawn-super-rich-kids]]
→ [[keep/2026-02-26-132809-2026-02-27t00-28-10-015-11-00]]

→ [[keep]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[2025-02-20-100802-about]]
→ [[2024-08-27-135521-cme-marketing-timeline]]
→ [[2025-02-13-051510-voice-chat-gpt4-summaries-13-02-25]]
→ [[2025-08-13-102831-2025-08-13t20-40-07-038-10-00]]
→ [[2025-11-15-163223-2025-11-16t03-32-26-033-11-00]]
→ [[2025-08-13-104011-2025-08-13t20-42-18-061-10-00]]

→ [[keep-index]]
→ [[2025-01-15-102135-sierra-tuna-notes]]
→ [[2025-08-12-045215-notes-for-thinkerbell-preso]]
→ [[2025-08-09-044150-soot-ash-residue-dynamics-in-dawn]]
→ [[2025-05-20-091739-linkedin-draft-20-5-25]]
→ [[2025-11-15-163002-2025-11-16t03-30-02-589-11-00]]

→ [[2025-02-20-075321-docker-and-celery-commands]]
→ [[2025-05-19-163744-server-scribble]]
→ [[2025-05-28-154122-dawn-test-1]]
→ [[2025-06-08-062357-fresh-termial-instate-gpt]]
→ [[2025-05-15-081254-2025-05-15t18-22-57-859-10-00]]
→ [[2025-10-06-150602-2025-10-07t02-07-04-211-11-00]]

→ [[2025-05-28-224414-2025-05-29t08-44-14-473-10-00]]
→ [[2025-03-03-074553-gti-commands]]
→ [[2025-08-18-101454-security]]
→ [[2025-05-27-104057-visual-suite]]
→ [[2025-09-19-041208-neofetch]]
→ [[2025-08-12-011708-a-disiplined-rebillion]]

→ [[2025-12-13-051108-formulas-13-12-25]]
→ [[2025-12-13-062815-miler-coat-of-arms]]
→ [[2025-12-12-032609-formulas-1212-25]]
→ [[2025-12-10-120936-2025-12-10t23-39-19-648-11-00]]
→ [[2025-07-14-082119-2025-07-14t18-21-19-769-10-00]]
→ [[2025-02-13-044420-conda-churn-final-env-packages]]

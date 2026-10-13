# MetroPulse

NYC taxi demand, weather, batch and replay quality, and late-event analytics.

This public dashboard reads a compact historical snapshot exported from local
Spark/Delta pipelines. It does not run Spark, Kafka, or PostgreSQL in the cloud.
Replay metrics are not live taxi traffic and must not be added to batch totals.
Controlled late-arrival tests are labeled separately from actual trip observations.

## Run

Use Python 3.11, install `requirements.txt`, then run `streamlit run dashboard.py`.

## Free deployment

Push this directory as a GitHub repository. In Streamlit Community Cloud choose
that repository, branch `main`, entrypoint `dashboard.py`, and Python 3.11 in
Advanced settings. No secrets are required. Choose public app sharing.

Updates require rerunning the local snapshot exporter and packaging script, then
pushing the resulting dashboard files. The hosted app works while the Mac is off;
pipeline processing remains local. Free hosting may sleep when inactive.

## Sources

- [NYC TLC trip records](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api)
- Weather data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

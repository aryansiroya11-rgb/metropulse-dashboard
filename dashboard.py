"""MetroPulse: read-only analytics over compact, versioned pipeline summaries."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

ROOT=Path(__file__).resolve().parent
SNAPSHOT=Path(os.getenv('METROPULSE_DASHBOARD_SNAPSHOT',str(ROOT/'snapshot.json')))
st.set_page_config(page_title='MetroPulse | NYC taxi analytics',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>
.block-container{padding-top:2.2rem;padding-bottom:3rem;max-width:1440px}
h1{font-size:2.5rem!important;font-weight:650!important;letter-spacing:-.03em}
h2{font-size:1.5rem!important;letter-spacing:-.02em}
h3{font-size:1.15rem!important}
[data-testid="stMetricValue"]{font-variant-numeric:tabular-nums;font-size:1.8rem}
[data-testid="stSidebar"]{border-right:1px solid #D7DED8}
[data-baseweb="tab-list"]{gap:1.5rem;border-bottom:1px solid #D7DED8}
a{text-underline-offset:3px} ::selection{background:#C9E4DB;color:#182E2B}
button:focus-visible,a:focus-visible{outline:3px solid #176B60!important;outline-offset:3px}
@media(max-width:700px){.block-container{padding-top:1rem}h1{font-size:2rem!important}[data-baseweb="tab-list"]{gap:.7rem}}
</style>''',unsafe_allow_html=True)

@st.cache_data(ttl=15)
def load_snapshot(path,modified):
    payload=json.loads(Path(path).read_text())
    if payload.get('schema_version')!=1 or not isinstance(payload.get('batches'),dict) or not isinstance(payload.get('streams'),dict):
        raise ValueError('Unsupported dashboard snapshot')
    return payload


def chart(frame,x,y,title,kind='line',color='#176B60',height=240):
    base=alt.Chart(frame).encode(x=alt.X(x,title=None),y=alt.Y(y,title=title),tooltip=list(frame.columns))
    result=base.mark_bar(color=color) if kind=='bar' else base.mark_line(color=color,strokeWidth=2.5,point=True)
    return result.properties(height=height).configure_view(stroke=None).configure_axis(gridColor='#E1E5DF',labelColor='#445B55',titleColor='#445B55')


def metrics(items):
    for column,(label,value,help_text) in zip(st.columns(len(items)),items):
        column.metric(label,value,help=help_text)


with st.sidebar:
    st.header('MetroPulse')
    st.caption('NYC mobility analytics')
    st.caption('Published historical snapshot. Updates are published by the project owner after local pipeline runs.')

st.title('MetroPulse')
st.write('Taxi demand, weather, and the quality of the data behind them.')
try:
    data=load_snapshot(str(SNAPSHOT),SNAPSHOT.stat().st_mtime_ns)
except (OSError,ValueError,KeyError):
    st.info('No readable dashboard snapshot yet. The project owner needs to publish a valid snapshot.')
    st.stop()
if not data['batches']:
    st.info('No published batch data is available yet. Complete a batch run, then refresh this dashboard.')
    st.stop()
when=datetime.fromisoformat(data['completed_at'])
age=(datetime.now(timezone.utc)-when).total_seconds()/60
st.caption(f"Historical NYC taxi data · Saved snapshot: {when.strftime('%d %b %Y, %H:%M UTC')} · {max(0,int(age))} minutes old")
st.caption('Public portfolio edition · Historical data, not a live taxi feed.')
for warning in data.get('warnings',[]):
    st.warning(warning)
with st.sidebar:
    month=st.selectbox('Batch month',sorted(data['batches'],reverse=True))
batch=data['batches'][month]
zone=pd.DataFrame(batch['zone_daily'])
weather=pd.DataFrame(batch['weather'])
if zone.empty or weather.empty:
    st.info('This month has no daily analytics or weather rows. Choose another month or refresh after a successful pipeline run.')
    st.stop()
zone['pickup_date']=pd.to_datetime(zone['pickup_date'])
weather['weather_date']=pd.to_datetime(weather['weather_date'])
with st.sidebar:
    dates=st.date_input('Date range',value=(weather.weather_date.min().date(),weather.weather_date.max().date()),min_value=weather.weather_date.min().date(),max_value=weather.weather_date.max().date())
    boroughs=st.multiselect('Pickup boroughs',sorted(zone.pickup_borough.unique()),default=sorted(zone.pickup_borough.unique()))
    st.caption('Date and borough filters apply to Demand & weather. Other tabs show their full batch or replay scope.')
    names=sorted(data['streams'])
    selected=st.selectbox('Streaming replay',names) if names else None
    st.divider()
    st.caption('Historical replay, not live taxi traffic. No pipeline heartbeat is inferred from this snapshot.')
if len(dates)!=2:
    st.info('Choose both a start and end date to view the selected period.')
    st.stop()
filtered=zone[zone.pickup_borough.isin(boroughs)&zone.pickup_date.between(pd.Timestamp(dates[0]),pd.Timestamp(dates[1]))]
w=weather[weather.weather_date.between(pd.Timestamp(dates[0]),pd.Timestamp(dates[1]))].copy()
stream=data['streams'].get(selected) if selected else None
trend,stream_tab,quality,late=st.tabs(['Demand & weather','Streaming','Data quality','Late arrivals'])
with trend:
    st.subheader('How the city moves')
    st.caption(f"Accepted trips · {dates[0]:%d %b}–{dates[1]:%d %b %Y} · {len(boroughs)} pickup boroughs")
    if filtered.empty:
        st.info('No trips match these filters. Select at least one borough or broaden the date range.')
    else:
        daily=filtered.groupby('pickup_date',as_index=False).agg(trips=('trip_count','sum'),charges_usd=('total_amount_usd','sum'))
        count=int(daily.trips.sum())
        metrics([('Accepted trips',f'{count:,}','After batch validation and exact-record deduplication.'),('Recorded charges',f'${daily.charges_usd.sum():,.0f}','TLC total amounts; not driver profit.'),('Trips per day',f'{count/len(w):,.0f}','Average across all calendar days in the selected period.')])
        daily=w[['weather_date']].rename(columns={'weather_date':'pickup_date'}).merge(daily,on='pickup_date',how='left').fillna(0)
        st.altair_chart(chart(daily,'pickup_date:T','trips:Q','Accepted trips',height=290),use_container_width=True)
        left,right=st.columns([1.15,1])
        with left:
            st.subheader('Most active pickup zones')
            top=filtered.groupby('pickup_zone',as_index=False).trip_count.sum().nlargest(10,'trip_count')
            bars=alt.Chart(top).mark_bar(color='#176B60').encode(x=alt.X('trip_count:Q',title='Accepted trips'),y=alt.Y('pickup_zone:N',sort='-x',title=None),tooltip=['pickup_zone','trip_count']).properties(height=300).configure_view(stroke=None)
            st.altair_chart(bars,use_container_width=True)
        with right:
            st.subheader('Weather through the month')
            st.caption('NYC reference location · Daily ERA5 estimates')
            st.altair_chart(chart(w[['weather_date','temperature_c']],'weather_date:T','temperature_c:Q','Temperature (°C)',height=140,color='#9B5209'),use_container_width=True)
            st.altair_chart(chart(w[['weather_date','precipitation_mm']],'weather_date:T','precipitation_mm:Q','Precipitation (mm)',kind='bar',height=140,color='#356F93'),use_container_width=True)
        st.caption('Weather is shared across boroughs from one NYC reference location. These trends do not establish a causal effect on demand.')
        st.download_button('Download filtered daily metrics',daily.to_csv(index=False),'metropulse-daily.csv','text/csv')
with stream_tab:
    st.subheader('From replay to reliable trips')
    if not stream:
        st.info('No streaming replay is available. Run a replay and refresh the snapshot.')
    else:
        st.caption(f"Replay: {selected} · Source month: {stream['month']} · Full replay scope")
        counts=stream['counts']
        metrics([('Kafka messages stored',f"{counts.get('bronze_messages',0):,}",'Includes repeat deliveries.'),('Accepted unique trips',f"{counts.get('accepted',0):,}",'Deduplicated, validated records.'),('Quarantined trips',f"{counts.get('quarantined',0):,}",'Failed business rules or malformed messages.')])
        st.info('Replay counts are a subset of the historical taxi dataset. Do not add them to the batch totals.')
        if stream['daily']:
            frame=pd.DataFrame(stream['daily'])
            frame['pickup_date']=pd.to_datetime(frame['pickup_date'])
            st.altair_chart(chart(frame,'pickup_date:T','trips:Q','Accepted replay trips',kind='bar',height=280),use_container_width=True)
        else:
            st.info('No accepted replay trips have been stored yet.')
        st.caption('The horizontal axis is the original pickup date, not when the replay ran. Snapshot data does not indicate whether the consumer is currently running.')
with quality:
    st.subheader('What passed, and what needs review')
    st.caption(f'Full batch · {month} · Date and borough filters do not apply')
    report=batch['report']; counts=report['counts']
    source=counts['source']; rejected=counts['quarantined']
    metrics([('Source rows',f'{source:,}','Original rows in the monthly taxi file.'),('Accepted',f"{counts['silver']:,}",'Rows published to Silver.'),('Quarantined',f'{rejected:,}','Retained for inspection.'),('Rejection rate',f'{100*rejected/source:.2f}%' if source else '—','Quarantined rows divided by source rows.')])
    reasons=pd.DataFrame([{'Reason':k.replace('_',' ').capitalize(),'Rows':v} for k,v in report['rejection_reasons'].items()])
    if not reasons.empty:
        st.altair_chart(alt.Chart(reasons).mark_bar(color='#9B5209').encode(x=alt.X('Rows:Q'),y=alt.Y('Reason:N',sort='-x',title=None),tooltip=['Reason','Rows']).properties(height=230).configure_view(stroke=None),use_container_width=True)
    st.caption('Reason counts overlap: one trip can fail several rules. Negative charges may represent refunds; quarantine does not mean every row is incorrect.')
    st.write(f"Reconciliation: {counts['silver']:,} accepted + {rejected:,} quarantined + {counts['exact_duplicates_removed']:,} exact duplicates removed = {source:,} source rows.")
    if stream:
        st.subheader('Replay validation')
        if stream['reasons']:
            st.dataframe(pd.DataFrame([{'Reason':k.replace('_',' ').capitalize(),'Rows':v} for k,v in stream['reasons'].items()]),hide_index=True,use_container_width=True)
        else:
            st.info('No rejection reasons recorded for the selected replay.')
with late:
    st.subheader('When late trips reach a closed window')
    if not stream:
        st.info('Choose a streaming replay with event-time aggregation to inspect lateness.')
    else:
        c=stream['counts']; p=stream['progress']
        st.caption(f'Replay: {selected} · Five-minute windows · Ten-minute lateness allowance')
        metrics([('Finalized windows',f"{c['finalized_windows']:,}" if 'finalized_windows' in c else '—','Only closed windows are published.'),('Trips in finalized windows',f"{c['finalized_trips']:,}" if 'finalized_trips' in c else '—','Not the full accepted-trip count.'),('Dropped from aggregation',str(p['dropped']) if p['dropped'] is not None else '—','Observed Spark watermark-drop metric. Trips remain in validated storage.')])
        if p['available']:
            st.write(f"**Latest recorded watermark (UTC):** {p['watermark'] or 'Not yet advanced'}")
            st.caption('The watermark follows observed pickup times, not wall-clock time. Idle streams can leave their newest windows open.')
            if 'finalized_trips' in c and 'accepted' in c:
                st.write(f"{c['accepted']-c['finalized_trips']:,} accepted trips are not represented in finalized windows. This can include open windows, late arrivals, or processing lag.")
            timeline=pd.DataFrame(p['timeline'])
            if not timeline.empty:
                timeline['observed_at']=pd.to_datetime(timeline['observed_at'])
                st.altair_chart(chart(timeline[['observed_at','dropped']],'observed_at:T','dropped:Q','Late rows dropped per recorded batch',kind='bar',height=200,color='#9B5209'),use_container_width=True)
        else:
            st.info('No aggregation progress has been recorded. Run the event-time stream, then refresh.')
        if stream['windows']:
            with st.expander('Finalized trips by UTC hour'):
                st.dataframe(pd.DataFrame(stream['windows']),hide_index=True,use_container_width=True)
    with st.expander('Controlled late-arrival test — separate from real replay metrics'):
        proof=data.get('controlled_test')
        if not proof:
            st.info('No controlled test evidence is available.')
        else:
            st.caption('Isolated test topic with controlled timestamps and amounts; these are test fixtures, not actual trip observations.')
            st.write(f"{proof['accepted_trips_retained']} unique test trips retained · {proof['finalized_trip_count']} finalized · {proof['too_late_dropped_from_aggregation']} too late for aggregates · {proof['still_open_window_trips']} still open")
            st.dataframe(pd.DataFrame([{'Arrival step':r['label'],'Pickup minutes (NYC)':', '.join(map(str,r['pickup_minutes'])),'Watermark UTC':r['watermark'],'Late drops so far':r['dropped_cumulative']} for r in proof['steps']]),hide_index=True,use_container_width=True)
with st.expander('Data sources and snapshot details'):
    st.write(f"Batch run completed: {batch['report']['completed_at']} · Weather coverage: {batch['report']['weather_days']} days")
    st.caption('The published snapshot comes from saved pipeline outputs; it does not fetch new taxi data or start a stream. Tables are individually versioned snapshots, not a single cross-pipeline transaction.')
    st.json({'batch_run':batch['report']['run_id'],'batch_versions':batch['versions'],'stream_versions':stream['versions'] if stream else None})
    st.markdown('[NYC Taxi & Limousine Commission](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) · [Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api) · [Weather attribution: CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)')

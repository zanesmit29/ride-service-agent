import requests, json, sys
user_id='test_user_123'
# create session
session_url=f'http://127.0.0.1:8000/apps/app/users/{user_id}/sessions'
resp=requests.post(session_url,json={'state':{'preferred_language':'English','visit_count':1}},timeout=10)
if resp.status_code!=200:
    print('session create failed', resp.status_code, resp.text)
    sys.exit(1)
session_id=resp.json()['id']
print('session', session_id)
# send streaming request
STREAM_URL='http://127.0.0.1:8000/run_sse'
headers={'Content-Type':'application/json','Accept':'text/event-stream'}
data={
    'app_name': 'app',
    'user_id': user_id,
    'session_id': session_id,
    'new_message': {
        'role': 'user',
        'parts': [{'text': 'Hi!'}],
    },
    'streaming': True,
}

r = requests.post(STREAM_URL, headers=headers, json=data, stream=True, timeout=60)
print('status', r.status_code)
events=[]
for line in r.iter_lines():
    if line:
        s=line.decode('utf-8')
        if s.startswith('data: '):
            payload=s[6:]
            try:
                obj=json.loads(payload)
                events.append(obj)
                print('EVENT', json.dumps(obj)[:200])
            except Exception as e:
                print('PARSE ERR', e, payload[:200])
    if len(events)>=3:
        break
print('received', len(events), 'events')

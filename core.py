from __future__ import annotations
import json, re
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo
import requests
import config
RIYADH=ZoneInfo('Asia/Riyadh')
POS=[('fda approval',95,'اعتماد FDA'),('acquisition',85,'استحواذ'),('merger agreement',80,'اندماج'),('strategic partnership',65,'شراكة'),('awarded contract',72,'عقد'),('contract award',72,'عقد'),('phase 3',75,'مرحلة ثالثة'),('positive topline',75,'نتائج إيجابية'),('beats estimates',62,'تفوق التوقعات'),('raises guidance',62,'رفع التوقعات')]
NEG=[('bankruptcy',-100,'إفلاس'),('chapter 11',-100,'إفلاس'),('delisting',-85,'خطر شطب'),('public offering',-75,'طرح'),('registered direct offering',-80,'طرح مباشر'),('at-the-market offering',-70,'بيع عبر السوق'),('warrant exercise',-55,'ضمانات'),('clinical hold',-90,'تعليق سريري'),('trial failed',-90,'فشل تجربة'),('misses estimates',-58,'دون التوقعات'),('lowers guidance',-65,'خفض التوقعات'),('reverse stock split',-50,'تجزئة عكسية'),('going concern',-65,'شكوك الاستمرارية')]
NOISE=['complete transcript','earnings call transcript','weekly recap','daily recap','top stories','morning brief']
def load_json(path:Path,default:Any):
 try:return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default
 except:return default
def save_json(path:Path,value:Any):
 path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');tmp.replace(path)
def load_control():
 d={'enabled':False,'positive_only':True,'ai_enabled':True};d.update(load_json(config.CONTROL_FILE,{}));return d
def update_control(**kw):
 d=load_control();d.update(kw);d['updated_at']=datetime.now(RIYADH).isoformat();save_json(config.CONTROL_FILE,d);return d
def load_account():
 d={'starting_balance_usd':5.0,'weekly_budget_usd':2.0,'ai_mode':'economic','last_daily_report':''};d.update(load_json(config.ACCOUNT_FILE,{}));return d
def save_account(d):save_json(config.ACCOUNT_FILE,d)
def load_symbols():return {x.strip().upper().replace('$','') for x in re.split(r'[\s,;]+',config.SYMBOLS_FILE.read_text(encoding='utf-8',errors='ignore')) if x.strip()}
def clean(v):return re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',str(v or ''))).strip()
def tickers(v):
 raw=re.split(r'[\s,;]+',v) if isinstance(v,str) else v if isinstance(v,list) else [v] if v else []
 out=[]
 for i in raw:
  s=str((i.get('symbol') or i.get('ticker') or '') if isinstance(i,dict) else i or '').strip().upper().replace('$','')
  if s and s not in out:out.append(s)
 return out
def parse_time(v):
 try:
  d=datetime.fromisoformat(str(v).replace('Z','+00:00'));return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
 except:return None
def ordinal_day(day):
 if 10 <= day % 100 <= 20:suffix='th'
 else:suffix={1:'st',2:'nd',3:'rd'}.get(day%10,'th')
 return f'{day}{suffix}'
def format_saudi_time(v):
 if not v:return '—'
 d=v if isinstance(v,datetime) else parse_time(v)
 if not d:return str(v)
 if not d.tzinfo:d=d.replace(tzinfo=timezone.utc)
 d=d.astimezone(RIYADH)
 return f"{d.strftime('%b')} {ordinal_day(d.day)} - {d.strftime('%I:%M%p').lower()}"
def sys_analyze(title,teaser):
 c=f'{title} {teaser}'.lower()
 if any(x in c for x in NOISE):return 0,'neutral','ضوضاء'
 hits=[x for x in POS+NEG if x[0] in c]
 if not hits:return 0,'neutral','لا توجد إشارة قوية'
 s=max(hits,key=lambda x:abs(x[1]))[1];r=[]
 for _,_,z in sorted(hits,key=lambda x:abs(x[1]),reverse=True):
  if z not in r:r.append(z)
 return s,'positive' if s>0 else 'negative','، '.join(r[:3])
def normalize(i):
 t=clean(i.get('title'));z=clean(i.get('teaser') or i.get('body'));p=str(i.get('published') or i.get('created') or '');s,se,r=sys_analyze(t,z);dt=parse_time(p)
 return {'id':str(i.get('benzinga_id') or i.get('id') or f'{p}:{t}'),'title':t or 'خبر بلا عنوان','teaser':z,'published':p,'published_display':format_saudi_time(dt),'url':str(i.get('url') or ''),'tickers':tickers(i.get('tickers') or i.get('stocks')),'system_score':int(s),'system_sentiment':se,'system_reason':r}
def extract(payload):
 if isinstance(payload,list):return payload
 if isinstance(payload,dict):
  for k in ('results','data','news'):
   if isinstance(payload.get(k),list):return payload[k]
 return []
def fetch_news(hours=None,limit=None):
 if not config.MASSIVE_API_KEY:raise RuntimeError('MASSIVE_API_KEY غير مضاف')
 params={'limit':limit or config.NEWS_LIMIT,'sort':'published.desc','apiKey':config.MASSIVE_API_KEY}
 if hours:params['published.gte']=(datetime.now(timezone.utc)-timedelta(hours=hours)).isoformat().replace('+00:00','Z')
 r=requests.get(config.MASSIVE_NEWS_URL,params=params,timeout=35)
 if r.status_code in (401,403):params.pop('apiKey',None);r=requests.get(config.MASSIVE_NEWS_URL,params=params,headers={'Authorization':f'Bearer {config.MASSIVE_API_KEY}'},timeout=35)
 r.raise_for_status();return extract(r.json())
def response_text(d):
 if d.get('output_text'):return str(d['output_text'])
 parts=[]
 for i in d.get('output',[]) if isinstance(d.get('output'),list) else []:
  if isinstance(i,dict):
   for c in i.get('content',[]):
    if isinstance(c,dict) and c.get('text'):parts.append(str(c['text']))
 return '\n'.join(parts)
def parse_obj(t):
 try:return json.loads(t)
 except:
  m=re.search(r'\{.*\}',t,re.S)
  if m:
   try:return json.loads(m.group(0))
   except:pass
 return {}
def record_usage(d,aid):
 u=d.get('usage') or {};it=int(u.get('input_tokens') or 0);ot=int(u.get('output_tokens') or 0);cost=it/1e6*config.OPENAI_INPUT_USD_PER_1M+ot/1e6*config.OPENAI_OUTPUT_USD_PER_1M
 led=load_json(config.USAGE_FILE,[]);led.append({'time':datetime.now(RIYADH).isoformat(),'article_id':aid,'input_tokens':it,'output_tokens':ot,'cost_usd':round(cost,8)});save_json(config.USAGE_FILE,led[-10000:]);return round(cost,8)
def ai_analyze(a):
 if not config.OPENAI_API_KEY:return {'score':0,'sentiment':'not_run','summary':'لم يتم تشغيل AI','reason':'المفتاح غير مضاف','squeeze_score':0,'dilution_risk':0,'cost_usd':0.0}
 prompt=f'''حلل خبر سهم أمريكي بشكل صارم. قد يكون الخبر الإيجابي ظاهريًا سلبيًا بسبب طرح أو تخفيف أو شطب أو تجزئة عكسية أو ضعف المحفز. أعد JSON فقط: {{"score": عدد -100 إلى 100, "sentiment":"positive|negative|neutral|mixed", "summary":"خلاصة عربية", "reason":"سبب عربي", "squeeze_score":0, "dilution_risk":0}}\nالرموز:{a.get('tickers')}\nالعنوان:{a.get('title')}\nالملخص:{a.get('teaser')}\nتقييم النظام:{a.get('system_score')}\nسبب النظام:{a.get('system_reason')}'''
 r=requests.post(config.OPENAI_URL,headers={'Authorization':f'Bearer {config.OPENAI_API_KEY}','Content-Type':'application/json'},json={'model':config.OPENAI_MODEL,'input':prompt,'temperature':0.1},timeout=45)
 if r.status_code==429:raise RuntimeError('OpenAI 429: الرصيد غير كافٍ أو تم تجاوز الحد')
 r.raise_for_status();d=r.json();o=parse_obj(response_text(d));o['score']=max(-100,min(100,int(o.get('score',0))));o['squeeze_score']=max(0,min(100,int(o.get('squeeze_score',0))));o['dilution_risk']=max(0,min(100,int(o.get('dilution_risk',0))));o['cost_usd']=record_usage(d,str(a.get('id')));return o
def ai_should(a,mode):
 s=abs(int(a.get('system_score',0)));return False if mode=='off' else s>=60 if mode=='economic' else s>=config.AI_ANALYZE_SYSTEM_MIN
def telegram_send(text):
 if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:return False,'بيانات تيليجرام ناقصة'
 r=requests.post(f'https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage',json={'chat_id':config.TELEGRAM_CHAT_ID,'text':text,'parse_mode':'HTML','disable_web_page_preview':True},timeout=25)
 try:d=r.json()
 except:d={}
 return (True,'تم الإرسال') if r.ok and d.get('ok') else (False,str(d.get('description') or r.text[:300]))
def article_message(a):
 ai=a.get('ai') or {};sy=' • '.join(a.get('tickers') or ['—']);url=a.get('url') or '';link=f'\n<a href="{escape(url)}">فتح الخبر</a>' if url else ''
 return f'<b>⚡ برق نيوز</b>\n<b>{escape(sy)}</b>\n<b>تقييم النظام:</b> {a.get("system_score",0)}\n<b>تقييم AI:</b> {ai.get("score","—")}\n<b>سكويز:</b> {ai.get("squeeze_score","—")}\n<b>خطر التخفيف:</b> {ai.get("dilution_risk","—")}\n<b>{escape(str(a.get("title","")))}</b>\n{escape(str(ai.get("summary") or "لم يتم تحليل AI"))}{link}'
def is_positive(a):
 ai=a.get('ai') or {};s=ai.get('sentiment')
 if s in ('negative','mixed'):return False
 if s=='positive':return int(ai.get('score',0))>=config.AI_POSITIVE_MIN
 return int(a.get('system_score',0))>=config.SYSTEM_POSITIVE_MIN
def process_articles(raw,hours,ai_enabled):
 wl=load_symbols();acc=load_account();cut=datetime.now(timezone.utc)-timedelta(hours=hours) if hours else None;out=[]
 for i in raw:
  a=normalize(i);m=sorted(set(a['tickers'])&wl)
  if not m:continue
  a['tickers']=m;pt=parse_time(a['published'])
  if cut and (not pt or pt<cut):continue
  if ai_enabled and ai_should(a,str(acc.get('ai_mode','economic'))):
   try:a['ai']=ai_analyze(a)
   except Exception as e:a['ai_error']=str(e);a['ai']={'score':0,'sentiment':'error','summary':'تعذر تحليل AI','reason':str(e),'squeeze_score':0,'dilution_risk':0,'cost_usd':0.0}
  out.append(a)
 return sorted(out,key=lambda x:x.get('published',''),reverse=True)
def usage_totals():
 led=load_json(config.USAGE_FILE,[]);today=datetime.now(RIYADH).date();week=today-timedelta(days=today.weekday());tot=tod=w=0.0
 for x in led:
  c=float(x.get('cost_usd',0));tot+=c
  try:d=datetime.fromisoformat(x['time']).astimezone(RIYADH).date()
  except:continue
  if d==today:tod+=c
  if d>=week:w+=c
 st=float(load_account().get('starting_balance_usd',0));return {'total_cost':round(tot,4),'today_cost':round(tod,4),'week_cost':round(w,4),'estimated_remaining':round(max(0,st-tot),4),'starting_balance':st}
def daily_openai_status():
 z=usage_totals();z.update({'connected':False,'message':'مفتاح OpenAI غير مضاف'})
 if not config.OPENAI_API_KEY:return z
 try:
  r=requests.post(config.OPENAI_URL,headers={'Authorization':f'Bearer {config.OPENAI_API_KEY}','Content-Type':'application/json'},json={'model':config.OPENAI_MODEL,'input':'Reply OK only','max_output_tokens':5},timeout=30)
  if r.ok:z.update({'connected':True,'message':'OpenAI يعمل والرصيد يسمح بطلب جديد'})
  elif r.status_code==429:z['message']='OpenAI أعاد 429: الرصيد غير كافٍ أو الحد متجاوز'
  else:z['message']=f'OpenAI HTTP {r.status_code}'
 except Exception as e:z['message']=f'تعذر الفحص: {e}'
 return z

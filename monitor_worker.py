from __future__ import annotations
import os,time,subprocess
from datetime import datetime
from zoneinfo import ZoneInfo
import config
from core import article_message,daily_openai_status,fetch_news,is_positive,load_account,load_control,load_json,process_articles,save_account,save_json,telegram_send
RIYADH=ZoneInfo('Asia/Riyadh')
def status(**kw):
 d=load_json(config.STATUS_FILE,{});d.update(kw);d['worker_pid']=os.getpid();d['updated_at']=datetime.now(RIYADH).isoformat();save_json(config.STATUS_FILE,d)
def lock():
 if config.WORKER_LOCK_FILE.exists():
  try:
   pid=int(config.WORKER_LOCK_FILE.read_text().strip())
   if os.name=='nt':
    r=subprocess.run(['tasklist','/FI',f'PID eq {pid}'],capture_output=True,text=True)
    if str(pid) in r.stdout:return False
   else:os.kill(pid,0);return False
  except:pass
 config.WORKER_LOCK_FILE.write_text(str(os.getpid()),encoding='utf-8');return True
def daily():
 a=load_account();today=datetime.now(RIYADH).date().isoformat()
 if a.get('last_daily_report')==today:return
 s=daily_openai_status();msg=f'<b>⚡ تقرير برق نيوز اليومي</b>\n<b>حالة OpenAI:</b> {s["message"]}\n<b>مصروف اليوم:</b> ${s["today_cost"]:.4f}\n<b>مصروف الأسبوع:</b> ${s["week_cost"]:.4f}\n<b>المتبقي التقديري:</b> ${s["estimated_remaining"]:.4f}\n<i>المتبقي تقديري حسب الرصيد المدخل، وليس رصيد OpenAI الرسمي.</i>'
 telegram_send(msg);a['last_daily_report']=today;save_account(a)

def send_heartbeat_if_needed():
    status = load_json(config.STATUS_FILE, {})
    now = datetime.now(RIYADH)
    last_value = status.get("last_heartbeat")
    last_heartbeat = None

    if last_value:
        try:
            last_heartbeat = datetime.fromisoformat(last_value)
            if last_heartbeat.tzinfo is None:
                last_heartbeat = last_heartbeat.replace(tzinfo=RIYADH)
        except Exception:
            last_heartbeat = None

    if last_heartbeat and (now - last_heartbeat).total_seconds() < 1800:
        return

    message = (
        "<b>⚡ برق نيوز</b>\n"
        "<b>✅ الرصد ما زال يعمل</b>\n"
        f"<b>الوقت:</b> {format_saudi_time(now)}\n"
        f"<b>آخر فحص:</b> {format_saudi_time(status.get('last_check'))}\n"
        f"<b>الأخبار المفحوصة:</b> {status.get('last_fetched', 0)}\n"
        f"<b>الإشعارات المرسلة:</b> {status.get('last_sent', 0)}"
    )

    ok, _ = telegram_send(message)
    if ok:
        status["last_heartbeat"] = now.isoformat()
        save_json(config.STATUS_FILE, status)


def run():
 if not lock():return
 status(worker_alive=True,monitoring=False,message='عامل الرصد يعمل')
 while True:
  try:
   daily();ctl=load_control()
   if not ctl.get('enabled'):
    status(worker_alive=True,monitoring=False,message='الرصد متوقف');time.sleep(2);continue
   status(worker_alive=True,monitoring=True,message='جارٍ فحص الأخبار')
   arts=process_articles(fetch_news(hours=2,limit=config.NEWS_LIMIT),2,bool(ctl.get('ai_enabled',True)))
   sent=set(map(str,load_json(config.SENT_FILE,[])));feed=load_json(config.FEED_FILE,[]);first=not sent;count=0
   for a in arts:
    aid=str(a['id'])
    if aid in sent:continue
    sent.add(aid);feed.insert(0,a)
    if is_positive(a) and not first:
     ok,_=telegram_send(article_message(a));count+=1 if ok else 0
   save_json(config.SENT_FILE,list(sent)[-10000:])
   seen=set();clean=[]
   for a in feed:
    aid=str(a.get('id'))
    if aid and aid not in seen:seen.add(aid);clean.append(a)
   save_json(config.FEED_FILE,clean[:1000]);status(worker_alive=True,monitoring=True,message='الرصد يعمل',last_check=datetime.now(RIYADH).isoformat(),last_fetched=len(arts),last_sent=count)
  except Exception as e:status(worker_alive=True,monitoring=True,message=f'خطأ الرصد: {e}',last_error=str(e))
  time.sleep(max(5,config.POLL_SECONDS))
if __name__=='__main__':
 try:run()
 finally:
  try:config.WORKER_LOCK_FILE.unlink(missing_ok=True)
  except:pass

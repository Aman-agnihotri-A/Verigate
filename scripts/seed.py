from __future__ import annotations
import os
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from pymongo import MongoClient
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.models.indexes import create_indexes
from app.security.masking import hash_value, mask_value

load_dotenv()

CLIENTS=[("alphabank","Alpha Bank","alpha-key",["127.0.0.1","103.24.10.5"],5),("zetafin","Zeta Fin","zeta-key",["127.0.0.1","103.24.10.6"],3),("novahr","Nova HR","nova-key",["127.0.0.1","103.24.10.7"],4)]

def _historical_log(cid:str,user:str,days_ago:int)->dict:
    id_number="ABCDE1234F"; name="Synthetic User"; code=random.choices(["VP2000","VP2001","VP2002","VP4003","VP4029","VP5001"],[55,10,10,5,15,5])[0]
    status={"VP2000":200,"VP2001":200,"VP2002":200,"VP4003":403,"VP4029":429,"VP5001":502}[code]
    fallback=code in {"VP2001","VP5001"}
    vendor="FALLBACK" if code=="VP2001" else ("PRIMARY" if code in {"VP2000","VP2002"} else None)
    return {"request_id":"req_"+uuid4().hex[:12],"client_id":cid,"user_id":user,"client_ref_id":f"SEED-{uuid4().hex[:12]}","ip":"198.51.100.99" if code=="VP4003" else next(c[3][1] for c in CLIENTS if c[0]==cid),"endpoint":"/api/v1/verify","id_type":"PAN","id_number_masked":mask_value(id_number),"id_number_hash":hash_value(id_number),"name_masked":mask_value(name),"name_hash":hash_value(name),"http_status":status,"error_code":code,"vendor_used":vendor,"fallback_used":fallback,"failover_reason":("VendorFailure" if fallback else None),"vendor_attempts":([{"vendor":"PRIMARY","outcome":"FAILED","error_type":"VendorFailure"},{"vendor":"FALLBACK","outcome":"SUCCESS"}] if code=="VP2001" else ([{"vendor":"PRIMARY","outcome":"FAILED","error_type":"VendorFailure"},{"vendor":"FALLBACK","outcome":"FAILED","error_type":"VendorFailure"}] if code=="VP5001" else ([{"vendor":"PRIMARY","outcome":"SUCCESS"}] if code in {"VP2000","VP2002"} else []))),"latency_ms":random.randint(100,900),"created_at":datetime.now(timezone.utc)-timedelta(days=days_ago,seconds=random.randint(0,86399))}

def main():
 db=MongoClient(os.getenv("MONGO_URI","mongodb://localhost:27017"))[os.getenv("MONGO_DB_NAME","verigate")]
 db.clients.delete_many({}); db.users.delete_many({}); db.api_logs.delete_many({})
 users=[]
 for cid,name,key,ips,tps in CLIENTS:
  db.clients.insert_one({"client_id":cid,"client_name":name,"api_key":key,"whitelisted_ips":ips,"tps_limit":tps,"status":"active"})
  current=[{"client_id":cid,"user_id":f"{cid[:2]}_ops_0{i}","status":"active"} for i in range(1,4)]; users.extend(current); db.users.insert_many(current)
 logs=[]
 for _ in range(3000):
  u=random.choice(users); logs.append(_historical_log(u["client_id"],u["user_id"],random.randint(0,29)))
 db.api_logs.insert_many(logs); create_indexes(db)
 print(f"Seeded {len(CLIENTS)} clients, {len(users)} users, {len(logs)} historical logs, and indexes")
if __name__=="__main__": main()

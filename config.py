from dotenv import load_dotenv
load_dotenv()   # pulls in any .env overrides
import os

DEFAULT_AUM     = float(os.getenv("DEFAULT_AUM", "30000000"))
RISK_FREE_RATE  = float(os.getenv("RISK_FREE_RATE", "0.025"))
REQUIRED_COLUMNS = ["Date", "GrossReturn"]

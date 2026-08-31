"""
Automated Tunnel Launcher for Member 1 NL-to-SQL API
Runs the FastAPI server and opens a public HTTPS ngrok tunnel for your team.
"""
import os
import sys
import time
import subprocess
import uvicorn
from dotenv import load_dotenv

load_dotenv()

def start():
    # Check for pyngrok
    try:
        from pyngrok import ngrok, conf
    except ImportError:
        print("[!] pyngrok is not installed. Please run: pip install pyngrok")
        sys.exit(1)

    port = 8000
    
    # Use local ngrok.exe if present in folder
    local_ngrok = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ngrok.exe")
    if os.path.exists(local_ngrok):
        pyngrok_config = conf.PyngrokConfig(ngrok_path=local_ngrok)
        conf.set_default(pyngrok_config)
        print(f"[+] Found local ngrok: {local_ngrok}")
    
    # Check if NGROK_AUTHTOKEN is in .env or system environment
    ngrok_token = os.getenv("NGROK_AUTHTOKEN")
    if ngrok_token:
        ngrok.set_auth_token(ngrok_token)
        print("[+] Set ngrok auth token from .env")
    else:
        print("[i] Hint: If you haven't added NGROK_AUTHTOKEN to your .env file,")
        print("    sign up at https://dashboard.ngrok.com/get-started/your-authtoken")
        print("    and add `NGROK_AUTHTOKEN=your_token_here` into .env\n")

    try:
        # Open an HTTP tunnel to port 8000
        tunnel = ngrok.connect(port, bind_tls=True)
        public_url = tunnel.public_url
        print("=" * 65)
        print(f"🚀 PUBLIC API IS LIVE AND READY FOR YOUR TEAM!")
        print(f"🔗 Public URL:  {public_url}")
        print(f"📖 Swagger Docs: {public_url}/docs")
        print(f"🎯 Translation:  {public_url}/api/v1/translate")
        print("=" * 65)
        print("\nShare the Swagger Docs link above with your team so they can test immediately from their laptops.\n")
    except Exception as e:
        print(f"[!] Could not start ngrok tunnel: {e}")
        print("[i] Falling back to local-only server on http://localhost:8000")

    # Start FastAPI server
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)

if __name__ == "__main__":
    start()

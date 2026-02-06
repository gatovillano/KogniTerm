import uvicorn
import os
import sys

# Change to the server directory if needed
os.chdir(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    uvicorn.run("kogniterm_server.main:app", host="0.0.0.0", port=8001, reload=True)

import subprocess, os, sys

os.chdir(r"C:\Users\xinzi\Desktop\DeepTutor\web")
node_dir = r"C:\Users\xinzi\AppData\Local\nvm\node-v20.19.0-win-x64"
env = os.environ.copy()
env["PATH"] = node_dir + ";" + env.get("PATH", "")
env["DEEPTUTOR_API_BASE_URL"] = "http://127.0.0.1:8001"

npx = os.path.join(node_dir, "npx.cmd")
subprocess.run([npx, "next", "dev", "--port", "3782"], env=env)

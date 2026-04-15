CYBER HAX ONLINE SHARE PACKAGE

What to send:
- cyber_hax_online.exe
- Play-Cyber-Hax-Online.bat

How to host:
1. On the host machine, run:
   uvicorn server_main:app --host 0.0.0.0 --port 8000
2. Forward port 8000 on the router if playing across the internet.
3. Give the other player your public IP address.

How to join:
1. Double-click Play-Cyber-Hax-Online.bat
2. Enter your player name
3. Use the same session name on both machines
4. For server URL, use:
   ws://HOST_PUBLIC_IP:8000

Example:
ws://203.0.113.10:8000

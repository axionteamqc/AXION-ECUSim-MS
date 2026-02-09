# RUN_ANDROID (Termux, no root)

1) Install Python:
```
pkg install python
```

2) Install deps (no pip upgrade):
```
pip install -r requirements.txt
```

3) Run:
```
chmod +x run_android.sh
./run_android.sh
```

Open: http://127.0.0.1:8000

Troubleshoot:
- Try PORT=/dev/ttyACM1 if the dongle changes.
- Example: PORT=/dev/ttyACM1 BITRATE=500000 ./run_android.sh

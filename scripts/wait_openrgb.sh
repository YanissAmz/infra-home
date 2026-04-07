#!/bin/bash
# Poll le port OpenRGB SDK jusqu'à ce qu'il réponde (max 60s)
for i in $(seq 1 60); do
    if timeout 1 bash -c "echo > /dev/tcp/127.0.0.1/6742" 2>/dev/null; then
        echo "[wait-openrgb] port 6742 ready after ${i}s"
        exit 0
    fi
    sleep 1
done
echo "[wait-openrgb] timeout 60s, starting anyway"
exit 0

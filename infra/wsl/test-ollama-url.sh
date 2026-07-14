#!/usr/bin/env bash
for url in \
  "http://127.0.0.1:11434/api/tags" \
  "http://10.255.255.254:11434/api/tags" \
  "http://$(ip route show default | awk '{print $3}'):11434/api/tags"
do
  echo "TRY $url"
  if curl -sf -m 3 "$url" >/dev/null; then
    echo "OK $url"
    exit 0
  fi
done
echo FAIL
exit 1

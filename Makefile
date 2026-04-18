PYTHON ?= python3

.PHONY: check restart-ha restart-ambilight deploy-ambilight

check:
	$(PYTHON) scripts/check_ambilight_stack.py
	$(PYTHON) -m py_compile scripts/ambilight_unified_sync.py
	$(PYTHON) -m unittest tests/test_govee_sink.py

restart-ha:
	docker restart homeassistant

restart-ambilight:
	sudo -n systemctl restart ambilight-sync.service

deploy-ambilight: check restart-ha restart-ambilight

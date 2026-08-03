# ------------------------------------------------------------------------------------------------ #
# Copyright (c) 2026 Carmenda. All rights reserved.                                                #
# This program is distributed under the terms of the PolyForm Noncommercial License 1.0.0          #
# ------------------------------------------------------------------------------------------------ #

.PHONY: up attach-deduce attach-deidentify

compose:
	docker compose up -d --build

watch-deduce:
	docker attach carmenda-deduce-engine

watch-deidentify:
	docker attach deidentify-engine

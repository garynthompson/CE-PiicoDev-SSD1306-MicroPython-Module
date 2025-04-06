#!/bin/bash

# To be manually called for minification
# Assumes uv for packaging and calling from root project folder.

uv run pyminify \
 --remove-literal-statements \
 PiicoDev_SSD1306.py > min/PiicoDev_SSD1306.py

uv run pyminify \
 --remove-literal-statements \
 --remove-unused-platforms \
 --platform-test-key "PLATFORM_BUILD" \
 --platform-preserve-value "microbit" \
 PiicoDev_SSD1306.py > min/PiicoDev_SSD1306_microbit.py

uv run pyminify \
 --remove-literal-statements \
 --remove-unused-platforms \
 --platform-test-key "PLATFORM_BUILD" \
 --platform-preserve-value "micropython" \
 PiicoDev_SSD1306.py > min/PiicoDev_SSD1306_micropython.py


#!/usr/bin/with-contenv bashio
set -e

# Remove settings used by retired test modes. Home Assistant retains saved app
# options across upgrades, so clean them through Supervisor before Python loads
# the new schema's options.
OPTIONS="$(bashio::addon.options)"
for old_key in provider test_audio_url media_file simulated_start_seconds mock_artist mock_title mock_album mock_year; do
    if bashio::jq.exists "${OPTIONS}" ".${old_key}"; then
        bashio::log.info "Removing obsolete option ${old_key}"
        bashio::addon.option "${old_key}"
    fi
done

exec /opt/venv/bin/python /app/main.py




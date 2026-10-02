#!/bin/sh
set -eu
git config core.hooksPath .githooks
printf 'Hooks del backend habilitados.\n'

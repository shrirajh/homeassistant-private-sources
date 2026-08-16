#!/bin/sh
# Hands credentials to git without putting them in argv or .git/config.
# git calls this with the prompt text as the first argument.
case "$1" in
    Username*) printf '%s' "${PSM_GIT_USERNAME}" ;;
    *)         printf '%s' "${PSM_GIT_PASSWORD}" ;;
esac

#!/bin/bash

# Read JSON input from stdin
input=$(cat)

# Extract values using grep and sed (no jq required)
# Extract current_dir from "workspace":{"current_dir":"value"}
current_dir=$(echo "$input" | grep -o '"workspace":{[^}]*"current_dir":"[^"]*"' | sed 's/.*"current_dir":"\([^"]*\)".*/\1/')

# Extract display_name from "model":{..."display_name":"value"}
model_display_name=$(echo "$input" | grep -o '"model":{[^}]*"display_name":"[^"]*"' | sed 's/.*"display_name":"\([^"]*\)".*/\1/')

# If display_name not found, try to extract "name" field from "model":{"name":"value"}
if [ -z "$model_display_name" ] || [ "$model_display_name" = "null" ]; then
    model_name_raw=$(echo "$input" | grep -o '"model":{[^}]*"name":"[^"]*"' | sed 's/.*"name":"\([^"]*\)".*/\1/')
fi

# If both display_name and name not found, try to extract "id" field from "model":{"id":"value"}
if ([ -z "$model_display_name" ] || [ "$model_display_name" = "null" ]) && ([ -z "$model_name_raw" ] || [ "$model_name_raw" = "null" ]); then
    model_id=$(echo "$input" | grep -o '"model":{[^}]*"id":"[^"]*"' | sed 's/.*"id":"\([^"]*\)".*/\1/')
fi

# If no object fields found, try model as direct string value "model":"value"
if ([ -z "$model_display_name" ] || [ "$model_display_name" = "null" ]) && ([ -z "$model_name_raw" ] || [ "$model_name_raw" = "null" ]) && ([ -z "$model_id" ] || [ "$model_id" = "null" ]); then
    model_string=$(echo "$input" | grep -o '"model":"[^"]*"' | sed 's/"model":"\([^"]*\)"/\1/')
fi

# Get user and hostname
user=$(whoami)
hostname=$(hostname -s)

# Use fallback values if parsing fails or returns empty
if [ -z "$current_dir" ]; then
    current_dir=$(pwd)
fi

# Parse model name into concise format
model_name="Claude"
if [ -n "$model_display_name" ] && [ "$model_display_name" != "null" ]; then
    # Extract model name and version from display name
    if echo "$model_display_name" | grep -q "Sonnet"; then
        version=$(echo "$model_display_name" | grep -o '[0-9]\+\.[0-9]\+' | head -1)
        model_name="Sonnet ${version:-3.5}"
    elif echo "$model_display_name" | grep -q "Opus"; then
        version=$(echo "$model_display_name" | grep -o '[0-9]\+\.[0-9]\+' | head -1)
        model_name="Opus ${version:-4.0}"
    elif echo "$model_display_name" | grep -q "Haiku"; then
        version=$(echo "$model_display_name" | grep -o '[0-9]\+\.[0-9]\+' | head -1)
        model_name="Haiku ${version:-3.0}"
    else
        model_name=$(echo "$model_display_name" | sed 's/Claude //g' | cut -d' ' -f1-2)
    fi
elif [ -n "$model_name_raw" ] && [ "$model_name_raw" != "null" ]; then
    case "$model_name_raw" in
        "opus"|"Opus")
            model_name="Opus 4.1"
            ;;
        "sonnet"|"Sonnet")
            model_name="Sonnet 3.5"
            ;;
        "haiku"|"Haiku")
            model_name="Haiku 3.0"
            ;;
        *)
            model_name=$(echo "$model_name_raw" | sed 's/^./\U&/')
            ;;
    esac
elif [ -n "$model_id" ] && [ "$model_id" != "null" ]; then
    model_from_id=$(echo "$model_id" | sed 's/claude-//g' | sed 's/-[0-9].*//g')
    case "$model_from_id" in
        "opus")
            version=$(echo "$model_id" | grep -o 'opus-[0-9]\+-[0-9]\+' | sed 's/opus-\([0-9]\+\)-\([0-9]\+\)/\1.\2/')
            model_name="Opus ${version:-4.1}"
            ;;
        "sonnet")
            version=$(echo "$model_id" | grep -o 'sonnet-[0-9]\+-[0-9]\+' | sed 's/sonnet-\([0-9]\+\)-\([0-9]\+\)/\1.\2/')
            model_name="Sonnet ${version:-3.5}"
            ;;
        "haiku")
            version=$(echo "$model_id" | grep -o 'haiku-[0-9]\+-[0-9]\+' | sed 's/haiku-\([0-9]\+\)-\([0-9]\+\)/\1.\2/')
            model_name="Haiku ${version:-3.0}"
            ;;
        *)
            model_name=$(echo "$model_from_id" | sed 's/^./\U&/')
            ;;
    esac
elif [ -n "$model_string" ] && [ "$model_string" != "null" ]; then
    case "$model_string" in
        "opus"|"Opus")
            model_name="Opus 4.1"
            ;;
        "sonnet"|"Sonnet")
            model_name="Sonnet 3.5"
            ;;
        "haiku"|"Haiku")
            model_name="Haiku 3.0"
            ;;
        *)
            model_name=$(echo "$model_string" | sed 's/^./\U&/')
            ;;
    esac
fi

# Format and output the status line matching bash PS1 format:
# green user@host, reset, colon, blue directory, reset, space, [model]
printf '\033[01;32m%s@%s\033[00m:\033[01;34m%s\033[00m [%s]' "$user" "$hostname" "$current_dir" "$model_name"

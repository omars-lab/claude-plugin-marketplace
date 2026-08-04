#!/usr/bin/env bash
#
# record.sh -- append one research finding, validated, to a shared CSV.
#
# This is the command a research subagent runs. One finding, one line, one
# invocation. It is deliberately the only sanctioned way to write these files:
# hand-editing them bypasses the checks, which is why a PostToolUse hook
# re-validates any file an agent writes directly.
#
#   record.sh init evidence  research/evidence.csv
#   record.sh init listings  research/listings.csv
#
#   record.sh evidence research/evidence.csv \
#       --candidate "Meridian M3" --criterion "Work envelope" \
#       --score 3 --grade A --value "260 mm long axis" \
#       --source-url "https://example.com/specs" --note "measured on the vendor drawing"
#
#   record.sh listing research/listings.csv \
#       --price 1250 --status sold --condition good --shipping local \
#       --location "Reno, NV" --source eBay --url "https://ebay.com/itm/..." \
#       --title "Meridian M3 + spare collets" --date 2026-07-14
#
#   record.sh check research/evidence.csv
#
# --retrieved defaults to today, because an undated record is unusable three
# weeks later and nobody remembers to pass it.
#
# Flags map to columns by turning dashes into underscores (--source-url ->
# source_url). Every rule that decides whether a row is acceptable lives in
# records.py, not here.

set -euo pipefail

HERE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ENGINE="$HERE/records.py"

usage() {
    sed -n '3,36p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit "${1:-1}"
}

[ $# -ge 1 ] || usage
case ${1:-} in -h|--help|help) usage 0 ;; esac
[ -f "$ENGINE" ] || { echo "record.sh: cannot find $ENGINE" >&2; exit 1; }

cmd=$1; shift

case "$cmd" in
    init)
        [ $# -eq 2 ] || { echo "record.sh: usage: record.sh init <evidence|listings> <file>" >&2; exit 1; }
        exec python3 "$ENGINE" init --kind "$1" --file "$2"
        ;;
    check)
        [ $# -eq 1 ] || { echo "record.sh: usage: record.sh check <file>" >&2; exit 1; }
        exec python3 "$ENGINE" check --file "$1"
        ;;
    evidence|listing|listings)
        [ "$cmd" = listing ] && cmd=listings
        [ $# -ge 1 ] || { echo "record.sh: usage: record.sh $cmd <file> --key value ..." >&2; exit 1; }
        file=$1; shift
        ;;
    *)
        echo "record.sh: unknown command '$cmd'" >&2
        usage
        ;;
esac

args=()
have_retrieved=0

while [ $# -gt 0 ]; do
    case $1 in
        --*)
            key=${1#--}
            key=${key//-/_}
            # Accept both `--key value` and `--key=value`.
            if [[ $key == *=* ]]; then
                val=${key#*=}
                key=${key%%=*}
            else
                shift
                [ $# -gt 0 ] || { echo "record.sh: --${key//_/-} needs a value" >&2; exit 1; }
                val=$1
            fi
            [ "$key" = retrieved ] && have_retrieved=1
            args+=(--set "$key=$val")
            shift
            ;;
        *)
            echo "record.sh: unexpected argument '$1' (flags look like --score 4)" >&2
            exit 1
            ;;
    esac
done

if [ "$have_retrieved" -eq 0 ]; then
    args+=(--set "retrieved=$(date +%Y-%m-%d)")
fi

exec python3 "$ENGINE" append --kind "$cmd" --file "$file" "${args[@]}"

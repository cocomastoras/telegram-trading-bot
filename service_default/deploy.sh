#!/bin/sh

NAME="$(basename $0)"
VERSION="v1"
PROJECT="placeholder-dev"


function usage {
    echo
    echo
    echo "DESCRIPTION"
    echo "   $NAME - deploy app engine service"
    echo
    echo "OPTIONAL PARAMETERS"
    echo "   --PROJECT=<placeholder-dev | placeholder-prod>  - Google cloud project to deploy to, defaults to 'placeholder-dev"
    echo "   --VERSION=<string>  - a version to deploy for app engine service, defaults to 'v1'"
    echo
    echo
    exit 1
}

while getopts :-: arg
do
  case $arg in
    -  )  LONG_OPTARG="${OPTARG#*=}"
    case $OPTARG in
        PROJECT=?*  )                   export PROJECT="$LONG_OPTARG" ;;
        VERSION=?*  )                   export VERSION="$LONG_OPTARG" ;;
      ''      )     break ;; # "--"
      *       )     usage >&2; exit 1 ;;
    esac ;;
    \? ) exit 1 ;;
  esac
done
shift $((OPTIND-1))

echo
if [ "$1" == "help" ]; then
    usage
fi

./requirements.sh
gcloud --project=${PROJECT} app deploy --version=${VERSION} --no-promote

#!/bin/bash

#========================================================================================================================#
# TEMPOROAL ADMIN-TOOLS ENTRYPOINT, taken from :                                                                         #
# https://github.com/tsurdilo/my-temporal-dockercompose/blob/825633a5d032420baaad8af19b487eba2b02eff0/script/setup.sh    #
#========================================================================================================================#
set -eux -o pipefail

# === Auto setup defaults ===

: "${DB:=postgres}"
: "${SKIP_SCHEMA_SETUP:=false}"
: "${SKIP_DB_CREATE:=false}"

# MySQL/PostgreSQL
: "${DBNAME:=temporal}"
: "${VISIBILITY_DBNAME:=temporal_visibility}"
: "${DB_PORT:=3306}"

: "${MYSQL_SEEDS:=}"
: "${MYSQL_USER:=}"
: "${MYSQL_PWD:=}"
: "${MYSQL_TX_ISOLATION_COMPAT:=false}"

: "${POSTGRES_SEEDS:=}"
: "${POSTGRES_USER:=}"
: "${POSTGRES_PWD:=}"


# Server setup
: "${TEMPORAL_CLI_ADDRESS:=}"

: "${SKIP_DEFAULT_NAMESPACE_CREATION:=false}"
: "${DEFAULT_NAMESPACE:=zane}"
: "${DEFAULT_NAMESPACE_RETENTION:=1d}"

: "${SKIP_ADD_CUSTOM_SEARCH_ATTRIBUTES:=false}"

# === Helper functions ===

die() {
    echo "$*" 1>&2
    exit 1
}

# === Main database functions ===

validate_db_env() {
    if [[ -z ${POSTGRES_SEEDS} ]]; then
        die "POSTGRES_SEEDS env must be set if DB is ${DB}."
    fi
}


wait_for_postgres() {
    until nc -z "${POSTGRES_SEEDS%%,*}" "${DB_PORT}"; do
        echo 'Waiting for PostgreSQL to startup.'
        sleep 1
    done

    echo 'PostgreSQL started.'
}

wait_for_db() {
    wait_for_postgres
}


setup_postgres_schema() {
    # TODO (alex): Remove exports
    { export SQL_PASSWORD=${POSTGRES_PWD}; } 2> /dev/null

    if [[ ${DB} == "postgres12" ]]; then
      POSTGRES_VERSION_DIR=v12
    else
      POSTGRES_VERSION_DIR=v96
    fi

    SCHEMA_DIR=${TEMPORAL_HOME}/schema/postgresql/${POSTGRES_VERSION_DIR}/temporal/versioned
    # Create database only if its name is different from the user name. Otherwise PostgreSQL container itself will create database.
    if [[ ${DBNAME} != "${POSTGRES_USER}" && ${SKIP_DB_CREATE} != true ]]; then
        temporal-sql-tool --plugin ${DB} --ep "${POSTGRES_SEEDS}" -u "${POSTGRES_USER}" -p "${DB_PORT}" --db "${DBNAME}" create
    fi
    temporal-sql-tool --plugin ${DB} --ep "${POSTGRES_SEEDS}" -u "${POSTGRES_USER}" -p "${DB_PORT}" --db "${DBNAME}" setup-schema -v 0.0
    temporal-sql-tool --plugin ${DB} --ep "${POSTGRES_SEEDS}" -u "${POSTGRES_USER}" -p "${DB_PORT}" --db "${DBNAME}" update-schema -d "${SCHEMA_DIR}"

    VISIBILITY_SCHEMA_DIR=${TEMPORAL_HOME}/schema/postgresql/${POSTGRES_VERSION_DIR}/visibility/versioned
    if [[ ${VISIBILITY_DBNAME} != "${POSTGRES_USER}" && ${SKIP_DB_CREATE} != true ]]; then
        temporal-sql-tool --plugin ${DB} --ep "${POSTGRES_SEEDS}" -u "${POSTGRES_USER}" -p "${DB_PORT}" --db "${VISIBILITY_DBNAME}" create
    fi
    temporal-sql-tool --plugin ${DB} --ep "${POSTGRES_SEEDS}" -u "${POSTGRES_USER}" -p "${DB_PORT}" --db "${VISIBILITY_DBNAME}" setup-schema -v 0.0
    temporal-sql-tool --plugin ${DB} --ep "${POSTGRES_SEEDS}" -u "${POSTGRES_USER}" -p "${DB_PORT}" --db "${VISIBILITY_DBNAME}" update-schema -d "${VISIBILITY_SCHEMA_DIR}"
}

setup_schema() {
     setup_postgres_schema
}

# === Server setup ===

register_default_namespace() {
    echo "Registering default namespace: ${DEFAULT_NAMESPACE}."
    if ! temporal operator namespace describe "${DEFAULT_NAMESPACE}"; then
        echo "Default namespace ${DEFAULT_NAMESPACE} not found. Creating..."
        temporal operator namespace create --retention "${DEFAULT_NAMESPACE_RETENTION}" --description "Default namespace for ZaneOps." --history-archival-state "enabled" --visibility-archival-state "enabled" --history-uri "file:///etc/temporal/archival/history" --visibility-uri "file:///etc/temporal/archival/visibility" "${DEFAULT_NAMESPACE}"
    else
        echo "Default namespace ${DEFAULT_NAMESPACE} already registered."
    fi
    echo "====== Default namespace ${DEFAULT_NAMESPACE} registration complete : ======"
    echo $(temporal operator namespace describe "${DEFAULT_NAMESPACE}")
    echo "====== END Default namespace ${DEFAULT_NAMESPACE} registration.       ======"
}

add_custom_search_attributes() {
    until temporal operator search-attribute list --namespace "${DEFAULT_NAMESPACE}"; do
      echo "Waiting for namespace cache to refresh..."
      sleep 1
    done
    echo "Namespace cache refreshed."

    echo "Adding Custom*Field search attributes."
    temporal operator search-attribute create --namespace "${DEFAULT_NAMESPACE}" \
        --name CustomKeywordField --type Keyword \
        --name CustomStringField --type Text \
        --name CustomTextField --type Text \
        --name CustomIntField --type Int \
        --name CustomDatetimeField --type Datetime \
        --name CustomDoubleField --type Double \
        --name CustomBoolField --type Bool
    echo "EXIT CODE=$?" 
}

setup_server(){
    until temporal operator cluster health | grep -q SERVING; do
        echo "Temporal CLI address: ${TEMPORAL_CLI_ADDRESS}."
        echo "Waiting for Temporal server to start..."
        sleep 1
    done
    echo "Temporal server started."

    if [[ ${SKIP_DEFAULT_NAMESPACE_CREATION} != true ]]; then
        register_default_namespace
    fi

    if [[ ${SKIP_ADD_CUSTOM_SEARCH_ATTRIBUTES} != true ]]; then
        add_custom_search_attributes
    fi
}

# === Main ===

if [[ ${SKIP_SCHEMA_SETUP} != true ]]; then
    validate_db_env
    wait_for_db
    setup_schema
fi

setup_server
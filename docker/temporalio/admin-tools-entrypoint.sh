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

# Validate required environment variables
: "${POSTGRES_SEEDS:?ERROR: POSTGRES_SEEDS environment variable is required}"
: "${POSTGRES_USER:?ERROR: POSTGRES_USER environment variable is required}"
: "${POSTGRES_PWD:?ERROR: POSTGRES_PWD environment variable is required}"


# Server setup
: "${TEMPORAL_CLI_ADDRESS:=}"

: "${SKIP_DEFAULT_NAMESPACE_CREATION:=false}"
: "${DEFAULT_NAMESPACE:=zane}"
: "${DEFAULT_NAMESPACE_RETENTION:=7d}"

: "${SKIP_ADD_CUSTOM_SEARCH_ATTRIBUTES:=false}"


# === Main database functions ===

wait_for_postgres() {
    echo 'Starting PostgreSQL schema setup...'
    echo 'Waiting for PostgreSQL port to be available...'
    nc -z -w 10 ${POSTGRES_SEEDS} ${DB_PORT:-5432}
    echo 'PostgreSQL port is available'
}


setup_postgres_schema() {
    { export SQL_PASSWORD=${POSTGRES_PWD}; } 2> /dev/null

    if [[ ${DB} == "postgres12" ]]; then
      POSTGRES_VERSION_DIR=v12
    else
      POSTGRES_VERSION_DIR=v96
    fi

    SCHEMA_DIR=${TEMPORAL_HOME}/schema/postgresql/${POSTGRES_VERSION_DIR}/temporal/versioned
    # Create database only if its name is different from the user name. Otherwise PostgreSQL container itself will create database.
    if [[ ${DBNAME} != "${POSTGRES_USER}" && ${SKIP_DB_CREATE} != true ]]; then
        temporal-sql-tool --plugin ${DB} --ep "${POSTGRES_SEEDS_CREATE}" -u "${POSTGRES_USER}" -p "${DB_PORT}" --db "${DBNAME}" create
    fi
    temporal-sql-tool --plugin ${DB} --ep "${POSTGRES_SEEDS}" -u "${POSTGRES_USER}" -p "${DB_PORT}" --db "${DBNAME}" setup-schema -v 0.0
    temporal-sql-tool --plugin ${DB} --ep "${POSTGRES_SEEDS}" -u "${POSTGRES_USER}" -p "${DB_PORT}" --db "${DBNAME}" update-schema -d "${SCHEMA_DIR}"

    VISIBILITY_SCHEMA_DIR=${TEMPORAL_HOME}/schema/postgresql/${POSTGRES_VERSION_DIR}/visibility/versioned
    if [[ ${VISIBILITY_DBNAME} != "${POSTGRES_USER}" && ${SKIP_DB_CREATE} != true ]]; then
        temporal-sql-tool --plugin ${DB} --ep "${POSTGRES_SEEDS_CREATE}" -u "${POSTGRES_USER}" -p "${DB_PORT}" --db "${VISIBILITY_DBNAME}" create
    fi
    temporal-sql-tool --plugin ${DB} --ep "${POSTGRES_SEEDS}" -u "${POSTGRES_USER}" -p "${DB_PORT}" --db "${VISIBILITY_DBNAME}" setup-schema -v 0.0
    temporal-sql-tool --plugin ${DB} --ep "${POSTGRES_SEEDS}" -u "${POSTGRES_USER}" -p "${DB_PORT}" --db "${VISIBILITY_DBNAME}" update-schema -d "${VISIBILITY_SCHEMA_DIR}"
}


# === Server setup ===

register_default_namespace() {
    echo "Registering default namespace: ${DEFAULT_NAMESPACE}."
    if ! temporal operator namespace describe "${DEFAULT_NAMESPACE}"; then
        echo "Default namespace ${DEFAULT_NAMESPACE} not found. Creating..."
        temporal operator namespace create --retention "${DEFAULT_NAMESPACE_RETENTION}" --description "Default namespace for ZaneOps." --history-archival-state "disabled" --visibility-archival-state "disabled" "${DEFAULT_NAMESPACE}"
    else
        echo "Default namespace ${DEFAULT_NAMESPACE} already registered, updating..."
        temporal operator namespace update --retention "${DEFAULT_NAMESPACE_RETENTION}" --description "Default namespace for ZaneOps." --history-archival-state "disabled" --visibility-archival-state "disabled" "${DEFAULT_NAMESPACE}"
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

wait_for_postgres
setup_postgres_schema

setup_server
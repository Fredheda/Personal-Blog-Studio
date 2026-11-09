import json

from conftest import FakeAz

SCRIPT = "scripts/setup-storage.sh"
ORIGIN = "https://blog-studio.frederikheda.com"

OTHER_RULE = {
    "name": "other-project-cleanup",
    "enabled": True,
    "type": "Lifecycle",
    "definition": {
        "filters": {"blobTypes": ["blockBlob"], "prefixMatch": ["other/"]},
        "actions": {"baseBlob": {"delete": {"daysAfterModificationGreaterThan": 7}}},
    },
}
OUR_RULE = {
    "name": "blog-drafts-uploads-30d",
    "enabled": True,
    "type": "Lifecycle",
    "definition": {
        "filters": {
            "blobTypes": ["blockBlob"],
            "prefixMatch": ["blog-drafts/uploads/"],
        },
        "actions": {"baseBlob": {"delete": {"daysAfterModificationGreaterThan": 30}}},
    },
}
# What `az storage account management-policy show` returns for the same rule:
# the service fills in extra null keys, so an exact comparison would report a
# change on every run.
OUR_RULE_AS_RETURNED = {
    "name": "blog-drafts-uploads-30d",
    "enabled": True,
    "type": "Lifecycle",
    "definition": {
        "filters": {
            "blobTypes": ["blockBlob"],
            "blobIndexMatch": None,
            "prefixMatch": ["blog-drafts/uploads/"],
        },
        "actions": {
            "baseBlob": {
                "delete": {
                    "daysAfterCreationGreaterThan": None,
                    "daysAfterModificationGreaterThan": 30,
                    "daysAfterLastAccessTimeGreaterThan": None,
                },
                "tierToCool": None,
                "tierToArchive": None,
                "enableAutoTierToHotFromCool": None,
            },
            "snapshot": None,
            "version": None,
        },
    },
}
# CORS rules in the shape the management API returns (arrays, camelCase).
OTHER_CORS_RULE = {
    "allowedOrigins": ["https://example.test"],
    "allowedMethods": ["GET"],
    "allowedHeaders": ["*"],
    "exposedHeaders": ["*"],
    "maxAgeInSeconds": 60,
}
CORS_OTHER = json.dumps([OTHER_CORS_RULE])
CORS_OURS = json.dumps(
    [
        {
            "allowedOrigins": [ORIGIN],
            "allowedMethods": ["OPTIONS", "PUT"],
            "allowedHeaders": ["x-ms-*", "content-type"],
            "exposedHeaders": ["x-ms-*"],
            "maxAgeInSeconds": 3600,
        }
    ]
)
ALL_ON = {"FAKE_BLOB_SD": "true", "FAKE_CONTAINER_SD": "true"}


def writes(fake_az: FakeAz) -> list[str]:
    prefixes = (
        "storage account blob-service-properties update",
        "storage account management-policy create",
    )
    return [c for c in fake_az.calls if c.startswith(prefixes)]


def cors_writes(fake_az: FakeAz) -> list[str]:
    return [c for c in writes(fake_az) if "cors.corsRules=" in c]


def cors_rules_written(call: str) -> list[dict]:
    return json.loads(call.split("cors.corsRules=", 1)[1])


def test_a_dry_run_prints_every_change_and_writes_nothing(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT)
    assert result.returncode == 0, result.stderr
    assert writes(fake_az) == []
    assert "+ az storage account blob-service-properties update" in result.stdout
    assert "cors.corsRules=" in result.stdout
    assert "--enable-delete-retention" in result.stdout
    assert "+ az storage account management-policy create" in result.stdout


def test_apply_adds_the_cors_rule_and_keeps_the_existing_ones(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, "--apply", env={**ALL_ON, "FAKE_CORS": CORS_OTHER})
    assert result.returncode == 0, result.stderr
    adds = cors_writes(fake_az)
    assert len(adds) == 1
    rules = cors_rules_written(adds[0])
    assert rules[0] == OTHER_CORS_RULE  # another project's rule is untouched
    assert rules[1] == {
        "allowedOrigins": [ORIGIN],
        "allowedMethods": ["OPTIONS", "PUT"],
        "allowedHeaders": ["x-ms-*", "content-type"],
        "exposedHeaders": ["x-ms-*"],
        "maxAgeInSeconds": 3600,
    }
    assert len(rules) == 2


def test_apply_adds_the_cors_rule_when_the_service_has_none(fake_az: FakeAz) -> None:
    # The management API returns null (not []) for a service that never had rules.
    result = fake_az.run(SCRIPT, "--apply", env={**ALL_ON, "FAKE_CORS": "null"})
    assert result.returncode == 0, result.stderr
    adds = cors_writes(fake_az)
    assert len(adds) == 1
    assert [r["allowedOrigins"] for r in cors_rules_written(adds[0])] == [[ORIGIN]]


def cors_reads(fake_az: FakeAz) -> list[str]:
    return [
        c
        for c in fake_az.calls
        if c.startswith("storage account blob-service-properties show")
        and "cors.corsRules" in c
    ]


def test_apply_reads_the_cors_rules_back_after_the_update(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, "--apply", env={**ALL_ON, "FAKE_CORS": CORS_OTHER})
    assert result.returncode == 0, result.stderr
    assert len(cors_reads(fake_az)) == 2  # before and after the update
    assert "CORS: verified" in result.stdout


def test_a_dry_run_does_not_read_back(fake_az: FakeAz) -> None:
    fake_az.run(SCRIPT, env=ALL_ON)
    assert len(cors_reads(fake_az)) == 1


def test_apply_fails_loudly_when_the_update_did_not_take_effect(
    fake_az: FakeAz,
) -> None:
    result = fake_az.run(
        SCRIPT,
        "--apply",
        env={**ALL_ON, "FAKE_CORS": CORS_OTHER, "FAKE_CORS_IGNORE_UPDATE": "1"},
    )
    assert result.returncode == 1
    assert "ERROR: CORS" in result.stderr and ORIGIN in result.stderr
    # It stops there: the lifecycle policy is not touched after a failed step.
    assert not [c for c in writes(fake_az) if "management-policy create" in c]


def test_apply_fails_loudly_when_the_update_dropped_other_rules(
    fake_az: FakeAz,
) -> None:
    result = fake_az.run(
        SCRIPT,
        "--apply",
        env={**ALL_ON, "FAKE_CORS": CORS_OTHER, "FAKE_CORS_DROP_OTHERS": "1"},
    )
    assert result.returncode == 1
    assert "ERROR: CORS" in result.stderr
    assert "existing" in result.stderr


def test_a_look_alike_origin_does_not_count_as_ours(fake_az: FakeAz) -> None:
    lookalike = json.dumps(
        [{**OTHER_CORS_RULE, "allowedOrigins": [f"{ORIGIN}.example.test"]}]
    )
    fake_az.run(SCRIPT, "--apply", env={**ALL_ON, "FAKE_CORS": lookalike})
    assert len(cors_writes(fake_az)) == 1


def test_the_origin_is_found_among_several_rules_and_origins(fake_az: FakeAz) -> None:
    several = json.dumps(
        [
            OTHER_CORS_RULE,
            {**OTHER_CORS_RULE, "allowedOrigins": ["https://a.test", ORIGIN]},
        ]
    )
    fake_az.run(SCRIPT, "--apply", env={**ALL_ON, "FAKE_CORS": several})
    assert cors_writes(fake_az) == []


def test_the_cors_rule_is_not_added_twice(fake_az: FakeAz) -> None:
    result = fake_az.run(SCRIPT, "--apply", env={**ALL_ON, "FAKE_CORS": CORS_OURS})
    assert result.returncode == 0, result.stderr
    assert cors_writes(fake_az) == []
    assert "already allowed" in result.stdout


def test_soft_delete_is_enabled_only_where_it_is_off(fake_az: FakeAz) -> None:
    result = fake_az.run(
        SCRIPT,
        "--apply",
        env={
            "FAKE_BLOB_SD": "true",
            "FAKE_CONTAINER_SD": "false",
            "FAKE_CORS": CORS_OURS,
        },
    )
    assert result.returncode == 0, result.stderr
    updates = [c for c in writes(fake_az) if "--enable-" in c]
    assert len(updates) == 1
    assert "--enable-container-delete-retention true" in updates[0]
    assert "--container-delete-retention-days 14" in updates[0]
    # The blob soft delete that is already on is not touched.
    assert "--enable-delete-retention" not in updates[0].replace(
        "--enable-container-delete-retention", ""
    )


def test_soft_delete_is_left_alone_when_both_are_on(fake_az: FakeAz) -> None:
    fake_az.run(SCRIPT, "--apply", env={**ALL_ON, "FAKE_CORS": CORS_OURS})
    assert not [c for c in writes(fake_az) if "--enable-" in c]


def policy_arg(call: str) -> dict:
    return json.loads(call.split("--policy ", 1)[1])


def test_the_lifecycle_rule_is_merged_with_the_existing_rules(fake_az: FakeAz) -> None:
    existing = json.dumps({"policy": {"rules": [OTHER_RULE]}})
    result = fake_az.run(
        SCRIPT,
        "--apply",
        env={**ALL_ON, "FAKE_CORS": CORS_OURS, "FAKE_POLICY": existing},
    )
    assert result.returncode == 0, result.stderr
    creates = [c for c in writes(fake_az) if "management-policy create" in c]
    assert len(creates) == 1
    names = [rule["name"] for rule in policy_arg(creates[0])["rules"]]
    assert names == ["other-project-cleanup", "blog-drafts-uploads-30d"]


def test_the_lifecycle_rule_is_created_when_there_is_no_policy(fake_az: FakeAz) -> None:
    fake_az.run(SCRIPT, "--apply", env={**ALL_ON, "FAKE_CORS": CORS_OURS})
    creates = [c for c in writes(fake_az) if "management-policy create" in c]
    assert [r["name"] for r in policy_arg(creates[0])["rules"]] == [OUR_RULE["name"]]


def test_an_identical_lifecycle_rule_is_not_written_again(fake_az: FakeAz) -> None:
    # Live-shaped: the returned rule carries extra null keys.
    existing = json.dumps({"policy": {"rules": [OTHER_RULE, OUR_RULE_AS_RETURNED]}})
    result = fake_az.run(
        SCRIPT,
        "--apply",
        env={**ALL_ON, "FAKE_CORS": CORS_OURS, "FAKE_POLICY": existing},
    )
    assert result.returncode == 0, result.stderr
    assert not [c for c in writes(fake_az) if "management-policy create" in c]
    assert "already present" in result.stdout


def test_a_changed_rule_of_ours_is_replaced_not_duplicated(fake_az: FakeAz) -> None:
    stale = {**OUR_RULE, "enabled": False}
    existing = json.dumps({"policy": {"rules": [stale, OTHER_RULE]}})
    fake_az.run(
        SCRIPT,
        "--apply",
        env={**ALL_ON, "FAKE_CORS": CORS_OURS, "FAKE_POLICY": existing},
    )
    creates = [c for c in writes(fake_az) if "management-policy create" in c]
    rules = policy_arg(creates[0])["rules"]
    assert [r["name"] for r in rules] == [
        "other-project-cleanup",
        "blog-drafts-uploads-30d",
    ]
    assert rules[1]["enabled"] is True

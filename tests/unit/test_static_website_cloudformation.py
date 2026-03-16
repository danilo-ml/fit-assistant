"""Tests for static website CloudFormation resources.

Validates that the CloudFormation template contains the required S3 bucket,
CloudFront distribution, OAC, and Outputs for the static website hosting.
"""

import os

import pytest
import yaml

TEMPLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "infrastructure", "template.yml"
)


class _CfnLoader(yaml.SafeLoader):
    """YAML loader that handles CloudFormation intrinsic function tags."""


# Register constructors for all CloudFormation intrinsic functions so that
# yaml.safe_load-equivalent parsing works on CF templates.
_CFN_TAGS = [
    "!Ref", "!Sub", "!GetAtt", "!Join", "!Select", "!Split",
    "!If", "!Not", "!Equals", "!And", "!Or", "!FindInMap",
    "!Base64", "!Cidr", "!ImportValue", "!GetAZs",
]

for _tag in _CFN_TAGS:
    _CfnLoader.add_multi_constructor(
        _tag,
        lambda loader, suffix, node: loader.construct_mapping(node, deep=True)
        if isinstance(node, yaml.MappingNode)
        else loader.construct_sequence(node, deep=True)
        if isinstance(node, yaml.SequenceNode)
        else loader.construct_scalar(node),
    )


@pytest.fixture(scope="module")
def template():
    with open(TEMPLATE_PATH, encoding="utf-8") as f:
        return yaml.load(f, Loader=_CfnLoader)  # noqa: S506


@pytest.fixture(scope="module")
def resources(template):
    return template["Resources"]


@pytest.fixture(scope="module")
def outputs(template):
    return template["Outputs"]


# --- StaticWebsiteBucket ---


class TestStaticWebsiteBucket:
    """Validate S3 bucket resource for static website."""

    def test_bucket_exists(self, resources):
        assert "StaticWebsiteBucket" in resources

    def test_bucket_type(self, resources):
        assert resources["StaticWebsiteBucket"]["Type"] == "AWS::S3::Bucket"

    def test_bucket_naming_pattern(self, resources):
        props = resources["StaticWebsiteBucket"]["Properties"]
        bucket_name = props["BucketName"]
        # CloudFormation !Sub produces a dict with "Fn::Sub"
        if isinstance(bucket_name, dict):
            name_str = bucket_name.get("Fn::Sub", "")
        else:
            name_str = str(bucket_name)
        assert "fitagent-static-website-${Environment}-${AWS::AccountId}" in name_str

    def test_public_access_block_all_blocked(self, resources):
        block = resources["StaticWebsiteBucket"]["Properties"][
            "PublicAccessBlockConfiguration"
        ]
        assert block["BlockPublicAcls"] is True
        assert block["BlockPublicPolicy"] is True
        assert block["IgnorePublicAcls"] is True
        assert block["RestrictPublicBuckets"] is True

    def test_bucket_encryption_aes256(self, resources):
        enc = resources["StaticWebsiteBucket"]["Properties"]["BucketEncryption"]
        rules = enc["ServerSideEncryptionConfiguration"]
        algorithms = [
            r["ServerSideEncryptionByDefault"]["SSEAlgorithm"] for r in rules
        ]
        assert "AES256" in algorithms


# --- StaticWebsiteCloudFrontOAC ---


class TestStaticWebsiteOAC:
    """Validate CloudFront Origin Access Control resource."""

    def test_oac_exists(self, resources):
        assert "StaticWebsiteCloudFrontOAC" in resources

    def test_oac_type(self, resources):
        assert (
            resources["StaticWebsiteCloudFrontOAC"]["Type"]
            == "AWS::CloudFront::OriginAccessControl"
        )

    def test_oac_origin_type_s3(self, resources):
        config = resources["StaticWebsiteCloudFrontOAC"]["Properties"][
            "OriginAccessControlConfig"
        ]
        assert config["OriginAccessControlOriginType"] == "s3"

    def test_oac_signing_behavior_always(self, resources):
        config = resources["StaticWebsiteCloudFrontOAC"]["Properties"][
            "OriginAccessControlConfig"
        ]
        assert config["SigningBehavior"] == "always"

    def test_oac_signing_protocol_sigv4(self, resources):
        config = resources["StaticWebsiteCloudFrontOAC"]["Properties"][
            "OriginAccessControlConfig"
        ]
        assert config["SigningProtocol"] == "sigv4"


# --- StaticWebsiteDistribution ---


class TestStaticWebsiteDistribution:
    """Validate CloudFront distribution resource."""

    def test_distribution_exists(self, resources):
        assert "StaticWebsiteDistribution" in resources

    def test_distribution_type(self, resources):
        assert (
            resources["StaticWebsiteDistribution"]["Type"]
            == "AWS::CloudFront::Distribution"
        )

    def test_viewer_protocol_redirect_to_https(self, resources):
        dist_config = resources["StaticWebsiteDistribution"]["Properties"][
            "DistributionConfig"
        ]
        policy = dist_config["DefaultCacheBehavior"]["ViewerProtocolPolicy"]
        assert policy == "redirect-to-https"

    def test_custom_error_response_403(self, resources):
        dist_config = resources["StaticWebsiteDistribution"]["Properties"][
            "DistributionConfig"
        ]
        error_responses = dist_config["CustomErrorResponses"]
        resp_403 = [r for r in error_responses if r["ErrorCode"] == 403]
        assert len(resp_403) == 1
        assert resp_403[0]["ResponsePagePath"] == "/erro.html"
        assert resp_403[0]["ResponseCode"] == 404

    def test_custom_error_response_404(self, resources):
        dist_config = resources["StaticWebsiteDistribution"]["Properties"][
            "DistributionConfig"
        ]
        error_responses = dist_config["CustomErrorResponses"]
        resp_404 = [r for r in error_responses if r["ErrorCode"] == 404]
        assert len(resp_404) == 1
        assert resp_404[0]["ResponsePagePath"] == "/erro.html"
        assert resp_404[0]["ResponseCode"] == 404


# --- Outputs ---


class TestStaticWebsiteOutputs:
    """Validate CloudFormation outputs for static website."""

    def test_bucket_name_output_exists(self, outputs):
        assert "StaticWebsiteBucketName" in outputs

    def test_website_url_output_exists(self, outputs):
        assert "StaticWebsiteUrl" in outputs

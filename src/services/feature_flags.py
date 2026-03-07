"""
Feature flag management for gradual rollout and per-trainer configuration.

This module provides feature flag checking for the multi-agent architecture
migration. It supports:
- Global feature flags (environment variables)
- Per-trainer feature flag overrides (DynamoDB)
- Graceful fallback to single-agent mode

The feature flag system enables:
- Phased rollout (10% → 50% → 100% of trainers)
- Emergency rollback without code deployment
- A/B testing of multi-agent vs single-agent
- Per-trainer opt-in/opt-out

Validates: Requirements 11.1, 11.2, 11.3
"""

from typing import Optional

from src.models.dynamodb_client import DynamoDBClient
from src.utils.logging import get_logger
from src.config import settings

logger = get_logger(__name__)


def is_multi_agent_enabled(trainer_id: str) -> bool:
    """
    Check if multi-agent architecture is enabled for a specific trainer.
    
    This function implements a two-level feature flag system:
    1. Global flag (settings.enable_multi_agent) - master switch
    2. Per-trainer override (DynamoDB FEATURE_FLAGS record) - granular control
    
    The logic:
    - If global flag is False, return False (multi-agent disabled globally)
    - If global flag is True, check per-trainer override
    - If no per-trainer override exists, default to True (enabled)
    - If per-trainer override exists, use its value
    
    This allows operators to:
    - Enable multi-agent globally, then opt-out specific trainers
    - Gradually roll out by enabling for specific trainers first
    - Emergency rollback by setting global flag to False
    
    Args:
        trainer_id: Trainer identifier
    
    Returns:
        True if multi-agent should be used, False for single-agent
    
    Examples:
        >>> # Global flag disabled - all trainers use single-agent
        >>> settings.enable_multi_agent = False
        >>> is_multi_agent_enabled('trainer_123')
        False
        
        >>> # Global flag enabled, no per-trainer override - use multi-agent
        >>> settings.enable_multi_agent = True
        >>> is_multi_agent_enabled('trainer_456')
        True
        
        >>> # Global flag enabled, per-trainer override to False
        >>> settings.enable_multi_agent = True
        >>> # (assuming DynamoDB has enable_multi_agent=False for trainer_789)
        >>> is_multi_agent_enabled('trainer_789')
        False
    """
    # Check global flag first
    if not settings.enable_multi_agent:
        logger.debug(
            "Multi-agent disabled globally",
            trainer_id=trainer_id,
        )
        return False
    
    # Check per-trainer override
    try:
        db_client = DynamoDBClient()
        
        # Query for trainer's feature flags
        flags = db_client.get_item(
            pk=f"TRAINER#{trainer_id}",
            sk="FEATURE_FLAGS",
        )
        
        if flags:
            # Per-trainer override exists
            enable_multi_agent = flags.get('enable_multi_agent', True)
            
            logger.info(
                "Using per-trainer feature flag",
                trainer_id=trainer_id,
                enable_multi_agent=enable_multi_agent,
            )
            
            return enable_multi_agent
        else:
            # No per-trainer override - default to enabled
            logger.debug(
                "No per-trainer override, defaulting to enabled",
                trainer_id=trainer_id,
            )
            return True
    
    except Exception as e:
        # If feature flag check fails, fall back to global setting
        logger.warning(
            "Failed to check per-trainer feature flag, using global setting",
            trainer_id=trainer_id,
            error=str(e),
        )
        return settings.enable_multi_agent


def set_trainer_feature_flag(
    trainer_id: str,
    enable_multi_agent: bool,
) -> bool:
    """
    Set per-trainer feature flag override.
    
    This function allows operators to enable/disable multi-agent for specific
    trainers without changing the global flag. Useful for:
    - Gradual rollout (enable for 10% of trainers)
    - Beta testing (enable for specific trainers)
    - Emergency rollback (disable for problematic trainers)
    
    Args:
        trainer_id: Trainer identifier
        enable_multi_agent: True to enable multi-agent, False for single-agent
    
    Returns:
        True if flag was set successfully, False otherwise
    
    Examples:
        >>> # Enable multi-agent for specific trainer
        >>> set_trainer_feature_flag('trainer_123', True)
        True
        
        >>> # Disable multi-agent for specific trainer
        >>> set_trainer_feature_flag('trainer_456', False)
        True
    """
    try:
        db_client = DynamoDBClient()
        
        # Create or update feature flags record
        db_client.put_item({
            'PK': f'TRAINER#{trainer_id}',
            'SK': 'FEATURE_FLAGS',
            'entity_type': 'FEATURE_FLAGS',
            'trainer_id': trainer_id,
            'enable_multi_agent': enable_multi_agent,
            'updated_at': datetime.utcnow().isoformat(),
        })
        
        logger.info(
            "Set per-trainer feature flag",
            trainer_id=trainer_id,
            enable_multi_agent=enable_multi_agent,
        )
        
        return True
    
    except Exception as e:
        logger.error(
            "Failed to set per-trainer feature flag",
            trainer_id=trainer_id,
            error=str(e),
        )
        return False


def get_rollout_percentage() -> float:
    """
    Calculate the percentage of trainers with multi-agent enabled.
    
    This function scans all trainers and calculates what percentage
    have multi-agent enabled (either by global flag or per-trainer override).
    
    Useful for monitoring gradual rollout progress.
    
    Returns:
        Percentage of trainers with multi-agent enabled (0.0 to 100.0)
    
    Examples:
        >>> get_rollout_percentage()
        45.5  # 45.5% of trainers have multi-agent enabled
    """
    try:
        db_client = DynamoDBClient()
        
        # Scan for all trainers
        # Note: In production, consider using a GSI or maintaining a counter
        response = db_client.table.scan(
            FilterExpression='entity_type = :entity_type',
            ExpressionAttributeValues={':entity_type': 'TRAINER'}
        )
        
        trainers = response.get('Items', [])
        total_trainers = len(trainers)
        
        if total_trainers == 0:
            return 0.0
        
        # Count trainers with multi-agent enabled
        enabled_count = 0
        for trainer in trainers:
            trainer_id = trainer.get('trainer_id')
            if is_multi_agent_enabled(trainer_id):
                enabled_count += 1
        
        percentage = (enabled_count / total_trainers) * 100
        
        logger.info(
            "Calculated rollout percentage",
            total_trainers=total_trainers,
            enabled_count=enabled_count,
            percentage=round(percentage, 2),
        )
        
        return round(percentage, 2)
    
    except Exception as e:
        logger.error(
            "Failed to calculate rollout percentage",
            error=str(e),
        )
        return 0.0


# Import datetime for timestamp
from datetime import datetime

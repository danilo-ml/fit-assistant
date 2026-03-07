"""
DynamoDB client abstraction layer for FitAgent.

This module provides a high-level interface for all DynamoDB operations
following the single-table design pattern with support for GSI queries.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key, Attr
from botocore.exceptions import ClientError


class DynamoDBClient:
    """
    DynamoDB client abstraction providing high-level methods for all access patterns.
    
    Supports single-table design with composite keys (PK, SK) and three GSIs:
    - phone-number-index: User identification by phone number
    - session-date-index: Session queries by trainer and date range
    - payment-status-index: Payment tracking by status
    """
    
    def __init__(self, table_name: Optional[str] = None, endpoint_url: Optional[str] = None):
        """
        Initialize DynamoDB client.
        
        Args:
            table_name: DynamoDB table name (defaults to DYNAMODB_TABLE env var)
            endpoint_url: AWS endpoint URL (for LocalStack, defaults to AWS_ENDPOINT_URL env var)
        """
        self.table_name = table_name or os.getenv('DYNAMODB_TABLE', 'fitagent-main')
        
        # Configure boto3 client
        config = {}
        if endpoint_url or os.getenv('AWS_ENDPOINT_URL'):
            config['endpoint_url'] = endpoint_url or os.getenv('AWS_ENDPOINT_URL')
        
        self.dynamodb = boto3.resource('dynamodb', **config)
        self.table = self.dynamodb.Table(self.table_name)
    
    # ==================== Core CRUD Operations ====================
    
    def get_item(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        """
        Get a single item by primary key.
        
        Args:
            pk: Partition key value
            sk: Sort key value
        
        Returns:
            Item dict if found, None otherwise
        """
        try:
            response = self.table.get_item(Key={'PK': pk, 'SK': sk})
            return self._deserialize_item(response.get('Item'))
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                return None
            raise
    
    def put_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Put an item into the table.
        
        Args:
            item: Item dict with PK and SK keys
        
        Returns:
            The item that was put
        """
        serialized_item = self._serialize_item(item)
        self.table.put_item(Item=serialized_item)
        return item
    
    def delete_item(self, pk: str, sk: str) -> bool:
        """
        Delete an item by primary key.
        
        Args:
            pk: Partition key value
            sk: Sort key value
        
        Returns:
            True if deleted, False if not found
        """
        try:
            self.table.delete_item(Key={'PK': pk, 'SK': sk})
            return True
        except ClientError:
            return False
    
    def query(
        self,
        key_condition_expression,
        filter_expression=None,
        index_name: Optional[str] = None,
        limit: Optional[int] = None,
        scan_index_forward: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Query items with key condition and optional filter.
        
        Args:
            key_condition_expression: boto3 Key condition expression
            filter_expression: Optional boto3 Attr filter expression
            index_name: Optional GSI name
            limit: Optional max items to return
            scan_index_forward: Sort order (True=ascending, False=descending)
        
        Returns:
            List of matching items
        """
        query_params = {
            'KeyConditionExpression': key_condition_expression,
            'ScanIndexForward': scan_index_forward
        }
        
        if filter_expression:
            query_params['FilterExpression'] = filter_expression
        if index_name:
            query_params['IndexName'] = index_name
        if limit:
            query_params['Limit'] = limit
        
        try:
            response = self.table.query(**query_params)
            items = [self._deserialize_item(item) for item in response.get('Items', [])]
            
            # Handle pagination if needed
            while 'LastEvaluatedKey' in response and (not limit or len(items) < limit):
                query_params['ExclusiveStartKey'] = response['LastEvaluatedKey']
                response = self.table.query(**query_params)
                items.extend([self._deserialize_item(item) for item in response.get('Items', [])])
            
            return items
        except ClientError:
            return []
    
    # ==================== Trainer Operations ====================
    
    def get_trainer(self, trainer_id: str) -> Optional[Dict[str, Any]]:
        """Get trainer by ID."""
        return self.get_item(f'TRAINER#{trainer_id}', 'METADATA')
    
    def put_trainer(self, trainer: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update trainer."""
        return self.put_item(trainer)
    
    def get_trainer_config(self, trainer_id: str) -> Optional[Dict[str, Any]]:
        """Get trainer configuration."""
        return self.get_item(f'TRAINER#{trainer_id}', 'CONFIG')
    
    def put_trainer_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update trainer configuration."""
        return self.put_item(config)
    
    def get_calendar_config(self, trainer_id: str) -> Optional[Dict[str, Any]]:
        """Get calendar configuration for trainer."""
        return self.get_item(f'TRAINER#{trainer_id}', 'CALENDAR_CONFIG')
    
    def put_calendar_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update calendar configuration."""
        return self.put_item(config)
    
    # ==================== Student Operations ====================
    
    def get_student(self, student_id: str) -> Optional[Dict[str, Any]]:
        """Get student by ID."""
        return self.get_item(f'STUDENT#{student_id}', 'METADATA')
    
    def put_student(self, student: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update student."""
        return self.put_item(student)
    
    # ==================== Trainer-Student Link Operations ====================
    
    def get_trainer_student_link(self, trainer_id: str, student_id: str) -> Optional[Dict[str, Any]]:
        """Get trainer-student link."""
        return self.get_item(f'TRAINER#{trainer_id}', f'STUDENT#{student_id}')
    
    def put_trainer_student_link(self, link: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update trainer-student link."""
        return self.put_item(link)
    
    def get_trainer_students(self, trainer_id: str) -> List[Dict[str, Any]]:
        """Get all students for a trainer."""
        return self.query(
            key_condition_expression=Key('PK').eq(f'TRAINER#{trainer_id}') & Key('SK').begins_with('STUDENT#')
        )
    
    def get_student_trainers(self, student_id: str) -> List[Dict[str, Any]]:
        """Get all trainers for a student."""
        return self.query(
            key_condition_expression=Key('PK').eq(f'STUDENT#{student_id}') & Key('SK').begins_with('TRAINER#')
        )
    
    # ==================== Session Operations ====================
    
    def get_session(self, trainer_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        return self.get_item(f'TRAINER#{trainer_id}', f'SESSION#{session_id}')
    
    def put_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update session."""
        return self.put_item(session)
    
    def get_trainer_sessions(self, trainer_id: str) -> List[Dict[str, Any]]:
        """Get all sessions for a trainer."""
        return self.query(
            key_condition_expression=Key('PK').eq(f'TRAINER#{trainer_id}') & Key('SK').begins_with('SESSION#')
        )
    
    def get_sessions_by_date_range(
        self,
        trainer_id: str,
        start_datetime: datetime,
        end_datetime: datetime,
        status_filter: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get sessions for a trainer within a date range using session-date-index GSI.
        
        Args:
            trainer_id: Trainer ID
            start_datetime: Start of date range
            end_datetime: End of date range
            status_filter: Optional list of statuses to filter by (e.g., ['scheduled', 'confirmed'])
        
        Returns:
            List of sessions within the date range
        """
        key_condition = Key('trainer_id').eq(trainer_id) & Key('session_datetime').between(
            start_datetime.isoformat(),
            end_datetime.isoformat()
        )
        
        filter_expr = None
        if status_filter:
            filter_expr = Attr('status').is_in(status_filter)
        
        return self.query(
            key_condition_expression=key_condition,
            filter_expression=filter_expr,
            index_name='session-date-index'
        )
    
    def get_upcoming_sessions(
        self,
        trainer_id: str,
        days_ahead: int = 30,
        status_filter: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get upcoming sessions for a trainer.
        
        Args:
            trainer_id: Trainer ID
            days_ahead: Number of days to look ahead (default 30)
            status_filter: Optional list of statuses to filter by
        
        Returns:
            List of upcoming sessions
        """
        now = datetime.utcnow()
        end_date = now + timedelta(days=days_ahead)
        return self.get_sessions_by_date_range(trainer_id, now, end_date, status_filter)
    
    def get_student_sessions(
        self,
        student_id: str,
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get sessions for a student, optionally filtered by date range.
        
        Note: This requires scanning since student_id is not a partition key.
        For production, consider adding a student-session GSI if this query is frequent.
        
        Args:
            student_id: Student ID
            start_datetime: Optional start of date range
            end_datetime: Optional end of date range
        
        Returns:
            List of sessions for the student
        """
        # Query all sessions and filter by student_id
        # This is not optimal but works for the single-table design
        # In production, consider adding a GSI with student_id as PK
        filter_expr = Attr('student_id').eq(student_id)
        
        if start_datetime and end_datetime:
            filter_expr = filter_expr & Attr('session_datetime').between(
                start_datetime.isoformat(),
                end_datetime.isoformat()
            )
        
        # We need to scan since we don't have a student-based index
        # This is acceptable for MVP but should be optimized with a GSI in production
        try:
            response = self.table.scan(FilterExpression=filter_expr)
            items = [self._deserialize_item(item) for item in response.get('Items', [])]
            
            # Handle pagination
            while 'LastEvaluatedKey' in response:
                response = self.table.scan(
                    FilterExpression=filter_expr,
                    ExclusiveStartKey=response['LastEvaluatedKey']
                )
                items.extend([self._deserialize_item(item) for item in response.get('Items', [])])
            
            # Sort by session_datetime
            items.sort(key=lambda x: x.get('session_datetime', ''))
            return items
        except ClientError:
            return []
    
    # ==================== Payment Operations ====================
    
    def get_payment(self, trainer_id: str, payment_id: str) -> Optional[Dict[str, Any]]:
        """Get payment by ID."""
        return self.get_item(f'TRAINER#{trainer_id}', f'PAYMENT#{payment_id}')
    
    def put_payment(self, payment: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update payment."""
        return self.put_item(payment)
    
    def get_trainer_payments(self, trainer_id: str) -> List[Dict[str, Any]]:
        """Get all payments for a trainer."""
        return self.query(
            key_condition_expression=Key('PK').eq(f'TRAINER#{trainer_id}') & Key('SK').begins_with('PAYMENT#')
        )
    
    def get_payments_by_status(
        self,
        trainer_id: str,
        status: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get payments by status using payment-status-index GSI.
        
        Args:
            trainer_id: Trainer ID
            status: Payment status ('pending' or 'confirmed')
            start_date: Optional start date for filtering (ISO format)
            end_date: Optional end date for filtering (ISO format)
        
        Returns:
            List of payments with the specified status
        """
        # The payment-status-index uses composite sort key: payment_status#created_at
        # We need to query with begins_with for the status
        key_condition = Key('trainer_id').eq(trainer_id) & Key('payment_status').begins_with(status)
        
        filter_expr = None
        if start_date and end_date:
            filter_expr = Attr('created_at').between(start_date, end_date)
        elif start_date:
            filter_expr = Attr('created_at').gte(start_date)
        elif end_date:
            filter_expr = Attr('created_at').lte(end_date)
        
        return self.query(
            key_condition_expression=key_condition,
            filter_expression=filter_expr,
            index_name='payment-status-index'
        )
    
    def get_student_payments(
        self,
        trainer_id: str,
        student_id: str,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get payments for a specific student.
        
        Args:
            trainer_id: Trainer ID
            student_id: Student ID
            status: Optional status filter
        
        Returns:
            List of payments for the student
        """
        key_condition = Key('PK').eq(f'TRAINER#{trainer_id}') & Key('SK').begins_with('PAYMENT#')
        filter_expr = Attr('student_id').eq(student_id)
        
        if status:
            filter_expr = filter_expr & Attr('payment_status').eq(status)
        
        return self.query(
            key_condition_expression=key_condition,
            filter_expression=filter_expr
        )
    
    # ==================== Conversation State Operations ====================
    
    def get_conversation_state(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Get conversation state by phone number."""
        return self.get_item(f'CONVERSATION#{phone_number}', 'STATE')
    
    def put_conversation_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update conversation state."""
        return self.put_item(state)
    
    def delete_conversation_state(self, phone_number: str) -> bool:
        """Delete conversation state."""
        return self.delete_item(f'CONVERSATION#{phone_number}', 'STATE')
    
    # ==================== Phone Number Lookup (GSI) ====================
    
    def lookup_by_phone_number(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """
        Look up user by phone number using phone-number-index GSI.
        
        Args:
            phone_number: Phone number in E.164 format
        
        Returns:
            User record (trainer or student) if found, None otherwise
        """
        results = self.query(
            key_condition_expression=Key('phone_number').eq(phone_number),
            index_name='phone-number-index',
            limit=1
        )
        return results[0] if results else None
    
    # ==================== Notification Operations ====================
    
    def get_notification(self, trainer_id: str, notification_id: str) -> Optional[Dict[str, Any]]:
        """Get notification by ID."""
        return self.get_item(f'TRAINER#{trainer_id}', f'NOTIFICATION#{notification_id}')
    
    def put_notification(self, notification: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update notification."""
        return self.put_item(notification)
    
    def get_trainer_notifications(self, trainer_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get notifications for a trainer."""
        return self.query(
            key_condition_expression=Key('PK').eq(f'TRAINER#{trainer_id}') & Key('SK').begins_with('NOTIFICATION#'),
            limit=limit,
            scan_index_forward=False  # Most recent first
        )
    
    # ==================== Reminder Operations ====================
    
    def get_reminder(self, session_id: str, reminder_id: str) -> Optional[Dict[str, Any]]:
        """Get reminder by ID."""
        return self.get_item(f'SESSION#{session_id}', f'REMINDER#{reminder_id}')
    
    def put_reminder(self, reminder: Dict[str, Any]) -> Dict[str, Any]:
        """Create or update reminder."""
        return self.put_item(reminder)
    
    def get_session_reminders(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all reminders for a session."""
        return self.query(
            key_condition_expression=Key('PK').eq(f'SESSION#{session_id}') & Key('SK').begins_with('REMINDER#')
        )
    
    # ==================== Batch Operations ====================
    
    def batch_get_items(self, keys: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Get multiple items in a single batch request.
        
        Args:
            keys: List of key dicts with 'PK' and 'SK' keys
        
        Returns:
            List of items found
        """
        if not keys:
            return []
        
        try:
            response = self.dynamodb.batch_get_item(
                RequestItems={
                    self.table_name: {
                        'Keys': keys
                    }
                }
            )
            items = response.get('Responses', {}).get(self.table_name, [])
            return [self._deserialize_item(item) for item in items]
        except ClientError:
            return []
    
    def batch_write_items(self, items: List[Dict[str, Any]]) -> bool:
        """
        Write multiple items in a single batch request.
        
        Args:
            items: List of items to write
        
        Returns:
            True if successful, False otherwise
        """
        if not items:
            return True
        
        try:
            with self.table.batch_writer() as batch:
                for item in items:
                    batch.put_item(Item=self._serialize_item(item))
            return True
        except ClientError:
            return False
    
    # ==================== Helper Methods ====================
    
    def _serialize_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Serialize item for DynamoDB (convert floats to Decimal).
        
        Args:
            item: Item dict
        
        Returns:
            Serialized item
        """
        serialized = {}
        for key, value in item.items():
            if isinstance(value, float):
                serialized[key] = Decimal(str(value))
            elif isinstance(value, dict):
                serialized[key] = self._serialize_item(value)
            elif isinstance(value, list):
                serialized[key] = [
                    self._serialize_item(v) if isinstance(v, dict) else
                    Decimal(str(v)) if isinstance(v, float) else v
                    for v in value
                ]
            else:
                serialized[key] = value
        return serialized
    
    def _deserialize_item(self, item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Deserialize item from DynamoDB (convert Decimal to float).
        
        Args:
            item: Item dict from DynamoDB
        
        Returns:
            Deserialized item
        """
        if item is None:
            return None
        
        deserialized = {}
        for key, value in item.items():
            if isinstance(value, Decimal):
                deserialized[key] = float(value)
            elif isinstance(value, dict):
                deserialized[key] = self._deserialize_item(value)
            elif isinstance(value, list):
                deserialized[key] = [
                    self._deserialize_item(v) if isinstance(v, dict) else
                    float(v) if isinstance(v, Decimal) else v
                    for v in value
                ]
            else:
                deserialized[key] = value
        return deserialized

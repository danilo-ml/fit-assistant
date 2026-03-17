# Requirements Document

## Introduction

The Admin Dashboard is a lightweight web interface for the FitAgent platform owner/administrator to monitor system-wide metrics and KPIs. Since the core product is WhatsApp-based, trainers and students do not use this dashboard — it is exclusively for the platform administrator to gain visibility into user activity, business health, growth trends, and system status. The dashboard queries DynamoDB (using existing GSIs and table scans) and AWS service metrics to present real-time and historical data.

## Glossary

- **Dashboard**: The web-based admin interface that displays system-wide KPIs and metrics
- **Dashboard_API**: The backend Lambda function that aggregates and serves metrics data to the Dashboard
- **Admin**: The FitAgent platform owner who accesses the Dashboard
- **Trainer**: A personal trainer registered on the FitAgent platform
- **Student**: A client linked to one or more Trainers on the platform
- **Session**: A scheduled training session between a Trainer and a Student
- **Payment**: A payment record registered by a Trainer for a Student
- **KPI_Card**: A visual component on the Dashboard that displays a single metric with its label and value
- **Time_Period_Selector**: A UI control that allows the Admin to choose the date range for metrics (e.g., today, 7 days, 30 days, custom)
- **DynamoDB_Client**: The existing abstraction layer for all DynamoDB operations

## Requirements

### Requirement 1: Admin Authentication

**User Story:** As an admin, I want to authenticate before accessing the dashboard, so that only authorized users can view system metrics.

#### Acceptance Criteria

1. WHEN an unauthenticated user accesses the Dashboard, THE Dashboard SHALL redirect the user to a login page
2. WHEN the Admin submits valid credentials, THE Dashboard SHALL grant access and display the main dashboard view
3. IF the Admin submits invalid credentials, THEN THE Dashboard SHALL display an error message and remain on the login page
4. WHILE the Admin is authenticated, THE Dashboard SHALL maintain the session for a maximum of 8 hours before requiring re-authentication
5. WHEN the Admin clicks the logout button, THE Dashboard SHALL terminate the session and redirect to the login page

### Requirement 2: Dashboard Overview Layout

**User Story:** As an admin, I want to see all key metrics on a single page, so that I can quickly assess the health of the platform.

#### Acceptance Criteria

1. THE Dashboard SHALL display KPI_Cards organized into four sections: User Metrics, Session Metrics, Payment Metrics, and Growth Metrics
2. THE Dashboard SHALL display the current date and time of the last data refresh
3. WHEN the Admin selects a time period using the Time_Period_Selector, THE Dashboard SHALL update all metrics to reflect the selected period
4. THE Time_Period_Selector SHALL support the following options: Today, Last 7 Days, Last 30 Days, and Custom Date Range
5. WHEN the Admin clicks the refresh button, THE Dashboard SHALL fetch the latest data from the Dashboard_API and update all KPI_Cards within 5 seconds

### Requirement 3: User Activity Metrics

**User Story:** As an admin, I want to see user activity metrics, so that I can understand how actively the platform is being used.

#### Acceptance Criteria

1. THE Dashboard SHALL display the total number of registered Trainers as a KPI_Card
2. THE Dashboard SHALL display the total number of registered Students as a KPI_Card
3. THE Dashboard SHALL display the number of distinct active Trainers within the selected time period as a KPI_Card, where active means the Trainer has at least one Session scheduled or completed in the period
4. THE Dashboard SHALL display the number of distinct active Students within the selected time period as a KPI_Card, where active means the Student has at least one Session scheduled or completed in the period
5. THE Dashboard SHALL display the average number of Students per Trainer as a KPI_Card
6. THE Dashboard SHALL display the total number of Trainer-Student links with status "active" as a KPI_Card

### Requirement 4: Session Metrics

**User Story:** As an admin, I want to see session-related KPIs, so that I can monitor training activity across the platform.

#### Acceptance Criteria

1. THE Dashboard SHALL display the total number of Sessions created within the selected time period as a KPI_Card
2. THE Dashboard SHALL display the number of Sessions with status "scheduled" within the selected time period as a KPI_Card
3. THE Dashboard SHALL display the number of Sessions with status "completed" within the selected time period as a KPI_Card
4. THE Dashboard SHALL display the number of Sessions with status "cancelled" within the selected time period as a KPI_Card
5. THE Dashboard SHALL display the number of Sessions with status "missed" within the selected time period as a KPI_Card
6. THE Dashboard SHALL display the session completion rate as a percentage, calculated as completed Sessions divided by the sum of completed and missed Sessions within the selected time period
7. THE Dashboard SHALL display the cancellation rate as a percentage, calculated as cancelled Sessions divided by total Sessions within the selected time period

### Requirement 5: Payment Metrics

**User Story:** As an admin, I want to see payment-related KPIs, so that I can track the financial health of the platform.

#### Acceptance Criteria

1. THE Dashboard SHALL display the total number of Payments registered within the selected time period as a KPI_Card
2. THE Dashboard SHALL display the number of Payments with status "pending" as a KPI_Card
3. THE Dashboard SHALL display the number of Payments with status "confirmed" within the selected time period as a KPI_Card
4. THE Dashboard SHALL display the total confirmed payment amount (sum of amount field for confirmed Payments) within the selected time period as a KPI_Card
5. THE Dashboard SHALL display the total pending payment amount (sum of amount field for pending Payments) as a KPI_Card
6. THE Dashboard SHALL display the payment confirmation rate as a percentage, calculated as confirmed Payments divided by total Payments within the selected time period
7. THE Dashboard SHALL display the average payment amount for confirmed Payments within the selected time period as a KPI_Card

### Requirement 6: Growth Metrics

**User Story:** As an admin, I want to see growth trends, so that I can understand how the platform is evolving over time.

#### Acceptance Criteria

1. THE Dashboard SHALL display the number of new Trainers registered within the selected time period as a KPI_Card
2. THE Dashboard SHALL display the number of new Students registered within the selected time period as a KPI_Card
3. THE Dashboard SHALL display a line chart showing the number of new Trainers registered per day over the selected time period
4. THE Dashboard SHALL display a line chart showing the number of new Students registered per day over the selected time period
5. THE Dashboard SHALL display a line chart showing the number of Sessions created per day over the selected time period
6. THE Dashboard SHALL display a line chart showing the total confirmed payment amount per day over the selected time period

### Requirement 7: Dashboard API

**User Story:** As an admin, I want the dashboard to load data efficiently, so that I can get insights without long wait times.

#### Acceptance Criteria

1. THE Dashboard_API SHALL expose a single GET endpoint that returns all aggregated metrics for a given time period
2. WHEN the Dashboard_API receives a request with start_date and end_date query parameters, THE Dashboard_API SHALL return metrics scoped to that date range
3. IF the Dashboard_API receives a request without date parameters, THEN THE Dashboard_API SHALL default to the last 30 days
4. THE Dashboard_API SHALL query DynamoDB using existing GSIs (session-date-index, payment-status-index) to minimize table scans
5. THE Dashboard_API SHALL return the response in JSON format with sections: user_metrics, session_metrics, payment_metrics, growth_metrics
6. IF the Dashboard_API encounters a DynamoDB query error, THEN THE Dashboard_API SHALL return a partial response with available data and include an errors array listing the failed sections
7. THE Dashboard_API SHALL complete the response within 10 seconds for any date range up to 90 days

### Requirement 8: Dashboard API Authentication

**User Story:** As an admin, I want the API to be secured, so that only the authenticated dashboard can access system metrics.

#### Acceptance Criteria

1. WHEN the Dashboard_API receives a request without a valid authorization token, THE Dashboard_API SHALL return HTTP 401 Unauthorized
2. THE Dashboard_API SHALL validate the authorization token on every request before processing
3. IF the authorization token is expired, THEN THE Dashboard_API SHALL return HTTP 401 with an error message indicating token expiration

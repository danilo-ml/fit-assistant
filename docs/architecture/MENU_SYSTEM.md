# Menu System Architecture

## Overview

FitAgent implements a **hybrid interaction model** combining structured menus with AI-powered natural language processing. The menu system provides a fallback mechanism for users who prefer structured navigation or when AI processing is unavailable.

## Architecture Decision

**Why Both Menus and AI?**

1. **User Preference**: Some users prefer structured menus over conversational AI
2. **Reliability**: Menus work even if AI service is down
3. **Discoverability**: Menus help users discover available features
4. **Onboarding**: New users can explore capabilities through menus
5. **Fallback**: If AI doesn't understand, offer menu options

## System Components

```
┌─────────────────────────────────────────────────────────┐
│                    Message Processor                     │
└────────────────────┬────────────────────────────────────┘
                     │
                     ▼
            ┌────────────────┐
            │ Message Router │
            └────────┬───────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
    ┌─────────┐           ┌──────────┐
    │ AI Path │           │Menu Path │
    └─────────┘           └────┬─────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
            ┌──────────┐ ┌──────────┐ ┌──────────┐
            │  Menu    │ │  Menu    │ │  Menu    │
            │Generator │ │Processor │ │ Context  │
            └──────────┘ └──────────┘ └──────────┘
```

## Core Components

### 1. MenuSystem (`menu_system.py`)
**Purpose**: Main orchestrator for menu-based interactions

**Responsibilities**:
- Determine if user is in menu mode or AI mode
- Route to appropriate menu handler
- Manage transitions between menu and AI modes

**Key Methods**:
- `process_menu_input()`: Process user input in menu context
- `should_use_menu()`: Decide if menu or AI should handle request
- `exit_menu_mode()`: Transition back to AI mode

### 2. MenuContext (`menu_context.py`)
**Purpose**: Manage menu navigation state

**State Structure**:
```python
{
    "phone_number": str,
    "current_menu": str,  # e.g., "main", "students", "sessions"
    "menu_path": List[str],  # Navigation history
    "selected_option": Optional[int],
    "context_data": Dict[str, Any],  # Menu-specific data
    "created_at": datetime,
    "expires_at": datetime,  # TTL: 30 minutes
}
```

**Storage**: DynamoDB with 30-minute TTL

**Key Methods**:
- `get_context()`: Retrieve current menu state
- `create_context()`: Initialize new menu session
- `update_context()`: Update menu state
- `clear_context()`: Exit menu mode

### 3. MenuDefinitions (`menu_definitions.py`)
**Purpose**: Define menu structure and options

**Menu Structure**:
```python
{
    "main": {
        "title": "Menu Principal",
        "options": [
            {
                "number": 1,
                "label": "Gerenciar Alunos",
                "action": "students_menu",
                "submenu": "students"
            },
            {
                "number": 2,
                "label": "Agendar Sessão",
                "action": "schedule_session",
                "requires_input": True
            },
            ...
        ]
    },
    "students": {
        "title": "Gerenciar Alunos",
        "parent": "main",
        "options": [...]
    }
}
```

**Menu Types**:
1. **Navigation Menus**: Lead to submenus
2. **Action Menus**: Execute tool functions
3. **Input Menus**: Collect user data
4. **List Menus**: Display data with pagination

### 4. MenuGenerator (`menu_generator.py`)
**Purpose**: Generate formatted menu text for WhatsApp

**Features**:
- Emoji support for visual appeal
- Numbered options for easy selection
- Breadcrumb navigation
- Back/Exit options
- Pagination for long lists

**Example Output**:
```
📋 Menu Principal

1️⃣ Gerenciar Alunos
2️⃣ Agendar Sessão
3️⃣ Ver Calendário
4️⃣ Registrar Pagamento
5️⃣ Enviar Notificação
6️⃣ Conectar Calendário

0️⃣ Sair do Menu

Digite o número da opção desejada.
```

### 5. MenuProcessor (`menu_processor.py`)
**Purpose**: Process user input and execute menu actions

**Input Processing**:
1. Parse user input (number selection or text)
2. Validate against current menu options
3. Execute action or navigate to submenu
4. Update menu context
5. Generate response

**Action Types**:
- `navigate`: Go to submenu
- `execute_tool`: Call AI agent tool function
- `collect_input`: Gather multi-step input
- `display_list`: Show paginated data
- `back`: Return to parent menu
- `exit`: Leave menu mode

## Menu Flow Examples

### Example 1: Register Student via Menu

```
User: /menu
Bot: 📋 Menu Principal
     1️⃣ Gerenciar Alunos
     ...

User: 1
Bot: 👥 Gerenciar Alunos
     1️⃣ Registrar Novo Aluno
     2️⃣ Ver Lista de Alunos
     3️⃣ Atualizar Aluno
     0️⃣ Voltar

User: 1
Bot: 📝 Registrar Novo Aluno
     
     Por favor, forneça as seguintes informações:
     Nome do aluno:

User: João Silva
Bot: Email do aluno:

User: joao@example.com
Bot: Telefone do aluno (formato: +5511999999999):

User: +5511999999999
Bot: Objetivo de treino:

User: Ganhar massa muscular
Bot: ✅ Aluno registrado com sucesso!
     
     Nome: João Silva
     Email: joao@example.com
     Telefone: +5511999999999
     Objetivo: Ganhar massa muscular
     
     Voltando ao menu...
```

### Example 2: View Calendar via Menu

```
User: /menu
Bot: 📋 Menu Principal
     ...
     3️⃣ Ver Calendário
     ...

User: 3
Bot: 📅 Ver Calendário
     
     1️⃣ Hoje
     2️⃣ Esta Semana
     3️⃣ Este Mês
     4️⃣ Data Específica
     0️⃣ Voltar

User: 2
Bot: 📅 Sessões - Esta Semana
     
     Segunda, 20 Jan
     • 14:00 - João Silva (60 min)
     • 16:00 - Maria Santos (45 min)
     
     Terça, 21 Jan
     • 10:00 - Pedro Costa (60 min)
     
     ...
     
     Total: 8 sessões
     
     0️⃣ Voltar ao Menu
```

## Menu vs AI Decision Logic

```python
def should_use_menu(message: str, context: MenuContext) -> bool:
    """
    Decide whether to use menu or AI for processing.
    
    Use menu if:
    - User explicitly requests menu (/menu command)
    - User is currently in menu context
    - User sends a number (menu selection)
    - AI is unavailable (fallback)
    
    Use AI if:
    - User sends natural language text
    - User explicitly exits menu (/ai command)
    - No active menu context
    """
    # Explicit menu request
    if message.lower() in ['/menu', 'menu']:
        return True
    
    # Explicit AI request
    if message.lower() in ['/ai', 'ai', 'sair do menu']:
        return False
    
    # Active menu context
    if context and not context.is_expired():
        return True
    
    # Number input (likely menu selection)
    if message.strip().isdigit():
        return True
    
    # Default to AI
    return False
```

## State Management

### Menu Context Lifecycle

1. **Creation**: User sends `/menu` command
2. **Active**: User navigates menus (30-minute TTL)
3. **Update**: Each interaction refreshes TTL
4. **Expiration**: Auto-deleted after 30 minutes of inactivity
5. **Exit**: User sends `/ai` or completes action

### Storage Pattern

**DynamoDB Item**:
```python
{
    "PK": "MENU_CONTEXT#{phone_number}",
    "SK": "STATE",
    "entity_type": "MENU_CONTEXT",
    "phone_number": "+5511999999999",
    "current_menu": "students",
    "menu_path": ["main", "students"],
    "context_data": {...},
    "created_at": "2024-01-20T10:00:00Z",
    "updated_at": "2024-01-20T10:05:00Z",
    "ttl": 1705752300  # Unix timestamp for auto-deletion
}
```

## Integration with AI Agent

### Hybrid Mode

The menu system and AI agent work together:

1. **Menu Collects Input** → **AI Executes Tool**
   - Menu gathers structured data
   - AI agent validates and executes tool function
   - Menu displays result

2. **AI Suggests Menu** → **User Chooses Menu**
   - AI doesn't understand request
   - Suggests relevant menu options
   - User can switch to menu mode

3. **Menu Shows Data** → **AI Provides Details**
   - Menu shows list of items
   - User asks AI for specific details
   - AI provides natural language explanation

### Example: Hybrid Session Scheduling

```
User: Agendar sessão
Bot: (AI) Com qual aluno você gostaria de agendar?

User: João
Bot: (AI) Quando você gostaria de agendar a sessão com João?

User: /menu
Bot: (Menu) 📅 Agendar Sessão
     
     Aluno: João Silva
     
     Escolha o dia:
     1️⃣ Hoje
     2️⃣ Amanhã
     3️⃣ Próxima Segunda
     4️⃣ Data Específica

User: 2
Bot: (Menu) Escolha o horário:
     1️⃣ 08:00
     2️⃣ 10:00
     3️⃣ 14:00
     4️⃣ 16:00
     5️⃣ Outro horário

User: 3
Bot: (AI executes schedule_session tool)
     ✅ Sessão agendada com sucesso!
     
     Aluno: João Silva
     Data: Amanhã, 21 Jan
     Horário: 14:00
     Duração: 60 minutos
```

## Performance Considerations

### Menu Context Caching

- **TTL**: 30 minutes (configurable)
- **Storage**: DynamoDB with automatic expiration
- **Size**: < 1 KB per context (minimal cost)

### Menu Generation

- **Pre-rendered**: Common menus cached in memory
- **Dynamic**: User-specific menus generated on-demand
- **Pagination**: Large lists split into pages (10 items per page)

## Error Handling

### Invalid Input

```python
if not is_valid_menu_option(user_input, current_menu):
    return (
        "❌ Opção inválida.\n\n"
        f"Por favor, escolha um número entre 0 e {max_option}.\n"
        "Ou digite 'menu' para ver as opções novamente."
    )
```

### Expired Context

```python
if menu_context.is_expired():
    menu_context.clear()
    return (
        "⏰ Sua sessão de menu expirou.\n\n"
        "Digite 'menu' para começar novamente ou "
        "continue com comandos de texto natural."
    )
```

### Menu Not Found

```python
if menu_id not in MENU_DEFINITIONS:
    logger.error("Menu not found", menu_id=menu_id)
    return (
        "❌ Erro ao carregar menu.\n\n"
        "Por favor, tente novamente ou use comandos de texto natural."
    )
```

## Future Enhancements

1. **Personalized Menus**: Show only relevant options based on user history
2. **Quick Actions**: Shortcuts for frequent operations
3. **Voice Menus**: Audio menu navigation for accessibility
4. **Multi-Language Menus**: Support for multiple languages
5. **Menu Analytics**: Track which menus are most used
6. **Smart Suggestions**: AI suggests menu shortcuts based on context

## Testing Strategy

### Unit Tests
- Menu generation formatting
- Input parsing and validation
- Context state transitions
- Action execution

### Integration Tests
- End-to-end menu flows
- Menu-to-AI transitions
- Multi-step input collection
- Error recovery

### User Acceptance Tests
- Real user navigation patterns
- Accessibility with screen readers
- Performance with large lists
- Mobile device compatibility

## Conclusion

The menu system provides a robust fallback and alternative interaction model for FitAgent. By combining structured menus with AI-powered natural language processing, we offer users flexibility in how they interact with the system while maintaining reliability and discoverability.

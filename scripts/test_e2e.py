#!/usr/bin/env python3
"""
Script de teste E2E para FitAgent.
Testa o fluxo completo: cadastro de personal e cadastro de aluno.
"""

import requests
import json
import time
from urllib.parse import urlencode

# Configuração
API_URL = "http://localhost:8000"
TRAINER_PHONE = "+5511940044117"  # Seu número de teste
TWILIO_NUMBER = "whatsapp:+14155238886"

def send_whatsapp_message(from_number: str, body: str):
    """Simula uma mensagem do Twilio WhatsApp."""
    
    # Dados do webhook do Twilio
    data = {
        "MessageSid": f"SM{int(time.time())}test",
        "From": f"whatsapp:{from_number}",
        "To": TWILIO_NUMBER,
        "Body": body,
        "NumMedia": "0"
    }
    
    print(f"\n📱 Enviando: '{body}'")
    print(f"   De: {from_number}")
    
    try:
        response = requests.post(
            f"{API_URL}/webhook",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )
        
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            print(f"   ✅ Mensagem processada")
            return True
        else:
            print(f"   ❌ Erro: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Exceção: {e}")
        return False

def check_health():
    """Verifica se a API está saudável."""
    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ API está saudável")
            return True
        else:
            print(f"❌ API retornou status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Erro ao verificar saúde da API: {e}")
        return False

def wait_for_processing(seconds=3):
    """Aguarda o processamento da mensagem."""
    print(f"   ⏳ Aguardando {seconds}s para processamento...")
    time.sleep(seconds)

def test_e2e_flow():
    """Testa o fluxo E2E completo."""
    
    print("=" * 60)
    print("🧪 TESTE E2E - FitAgent")
    print("=" * 60)
    
    # 1. Verificar saúde da API
    print("\n1️⃣ Verificando saúde da API...")
    if not check_health():
        print("\n❌ API não está disponível. Verifique se os containers estão rodando.")
        print("   Execute: docker-compose ps")
        return False
    
    # 2. Cadastro do Personal (Onboarding)
    print("\n2️⃣ Testando cadastro do personal (onboarding)...")
    if not send_whatsapp_message(TRAINER_PHONE, "Olá"):
        return False
    
    wait_for_processing(5)
    
    # 3. Saudação após cadastro
    print("\n3️⃣ Testando saudação após cadastro...")
    if not send_whatsapp_message(TRAINER_PHONE, "Oi"):
        return False
    
    wait_for_processing(3)
    
    # 4. Pedir ajuda
    print("\n4️⃣ Testando comando de ajuda...")
    if not send_whatsapp_message(TRAINER_PHONE, "O que você faz?"):
        return False
    
    wait_for_processing(3)
    
    # 5. Cadastrar aluno
    print("\n5️⃣ Testando cadastro de aluno...")
    if not send_whatsapp_message(
        TRAINER_PHONE, 
        "Cadastrar aluno João Silva telefone +5511988887777"
    ):
        return False
    
    wait_for_processing(3)
    
    # 6. Listar alunos
    print("\n6️⃣ Testando listagem de alunos...")
    if not send_whatsapp_message(TRAINER_PHONE, "Listar meus alunos"):
        return False
    
    wait_for_processing(3)
    
    # 7. Agendar sessão
    print("\n7️⃣ Testando agendamento de sessão...")
    if not send_whatsapp_message(TRAINER_PHONE, "Agendar treino"):
        return False
    
    wait_for_processing(3)
    
    print("\n" + "=" * 60)
    print("✅ TESTE E2E CONCLUÍDO!")
    print("=" * 60)
    print("\n📋 Próximos passos:")
    print("1. Verifique os logs: docker logs -f fitagent-sqs-processor")
    print("2. Verifique as mensagens no WhatsApp")
    print("3. Todas as respostas devem estar em português")
    print("\n💡 Dica: Se houver erros, verifique:")
    print("   - docker logs fitagent-sqs-processor | grep ERROR")
    print("   - docker logs fitagent-api | grep ERROR")
    
    return True

if __name__ == "__main__":
    success = test_e2e_flow()
    exit(0 if success else 1)

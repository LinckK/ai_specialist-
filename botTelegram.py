import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))
import telebot
from agent_project.config import get_default_config
from agent_project.agent import Agent
from agent_project.db import db

token = '8612341601:AAFJgviW4LP0_uuEfyOTRhh9ZY4b4o0rVqY';
bot = telebot.TeleBot(token);

@bot.message_handler(content_types=['text'])
def echo(msg: telebot.types.Message):
    user_text = msg.text
    try:
        globalAgentData = db.get_agent('global') #isso vai trocar dps
        synthesisAgentData = db.get_agent('sintetizador') #isso vai trocar dps
        specificAgentData = db.get_agent('specific') #isso vai trocar dps
        
        conversations = db.list_allConversationsByTelegramId(msg.from_user.id)
        conversation = conversations[0] if len(conversations) > 0 else db.create_conversation(None, msg.from_user.id);
        conv_id = str(conversation.id) if hasattr(conversation, 'id') else conversation.get('id')

        # 1. Enviar user_text para o agente global
        global_config = get_default_config()
        global_prompt = globalAgentData.get('config', {}).get('specialized_system_prompt', '') if globalAgentData else ''
        global_agent = Agent(config=global_config, specialized_prompt_override=global_prompt, conversation_id=conv_id)
        global_result = global_agent.run_loop(user_text)
        global_response = global_result.get("output", "Sem resposta.") if global_result.get("success") else f"Erro: {global_result.get('error', 'desconhecido')}"

        # 2. Enviar user_text para o agente específico
        specific_config = get_default_config()
        specific_prompt = specificAgentData.get('config', {}).get('specialized_system_prompt', '') if specificAgentData else ''
        specific_agent = Agent(config=specific_config, specialized_prompt_override=specific_prompt, conversation_id=conv_id)
        specific_result = specific_agent.run_loop(user_text)
        specific_response = specific_result.get("output", "Sem resposta.") if specific_result.get("success") else f"Erro: {specific_result.get('error', 'desconhecido')}"

        # 3. Combinar as duas respostas e enviar para o sintetizador
        synthesis_input = (
            f"Pergunta original do usuário: {user_text}\n\n"
            f"--- Resposta do Agente Global ---\n{global_response}\n\n"
            f"--- Resposta do Agente Específico ---\n{specific_response}\n\n"
            f"Por favor, sintetize as duas respostas acima em uma única resposta final coerente e completa para o usuário."
        )
        synthesis_config = get_default_config()
        synthesis_prompt = synthesisAgentData.get('config', {}).get('specialized_system_prompt', '') if synthesisAgentData else ''
        synthesis_agent = Agent(config=synthesis_config, specialized_prompt_override=synthesis_prompt, conversation_id=conv_id)
        synthesis_result = synthesis_agent.run_loop(synthesis_input)

        if synthesis_result.get("success"):
            resposta = synthesis_result.get("output", "Sem resposta do sintetizador.")
        else:
            resposta = f"Erro do sintetizador: {synthesis_result.get('error', 'desconhecido')}"
    except Exception as e:
        resposta = f"Erro ao processar: {str(e)}"

    bot.reply_to(msg, resposta)

bot.infinity_polling()
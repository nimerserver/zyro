import discord
from discord.ext import commands
import aiohttp
import asyncio
import json
import os
from config import DISCORD_TOKEN, GROQ_API_KEY

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =======================================================
# ARQUIVO DE HISTÓRICO
# =======================================================
HISTORY_FILE = "history.json"

if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w") as f:
        json.dump({}, f)


def get_history(user_id):
    with open(HISTORY_FILE, "r") as f:
        data = json.load(f)
    return data.get(str(user_id), [])


def add_history(user_id, role, content):
    with open(HISTORY_FILE, "r") as f:
        data = json.load(f)
    user_id_str = str(user_id)
    if user_id_str not in data:
        data[user_id_str] = []
    data[user_id_str].append({"role": role, "content": content})
    data[user_id_str] = data[user_id_str][-8:]
    with open(HISTORY_FILE, "w") as f:
        json.dump(data, f, indent=4)


# =======================================================
# BOT ONLINE
# =======================================================
@bot.event
async def on_ready():
    print(f"🤖 {bot.user} está online!")


# =======================================================
# FUNÇÃO GERAR RESPOSTA (API GROQ)
# =======================================================
async def gerar_resposta(user_id, texto):
    url = "https://api.groq.com/openai/v1/chat/completions"

    history = get_history(user_id)

    messages = [
        {
            "role": "system",
            "content": "Você é Zyro, um assistente divertido e animado do Discord! 🎉 Responda de forma curta e amigável."
        }
    ]

    for msg in history:
        messages.append(msg)

    messages.append({"role": "user", "content": texto})

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    json_data = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 500,
        "stream": False
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=json_data, timeout=25) as r:
                data = await r.json()

                if r.status != 200:
                    return f"⚠️ Erro {r.status}: {data}"

                reply = data["choices"][0]["message"]["content"].strip()

                add_history(user_id, "user", texto)
                add_history(user_id, "assistant", reply)

                return reply

    except asyncio.TimeoutError:
        return "⏰ A Groq demorou muito a responder!"
    except Exception as e:
        return f"⚠️ Erro: {str(e)[:100]}"


# =======================================================
# ON_MESSAGE - Menção ou resposta à mensagem do bot
# =======================================================
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if bot.user in message.mentions:
        content = message.content.replace(f"<@{bot.user.id}>", "").replace(f"<@!{bot.user.id}>", "").strip()
        if not content:
            await message.reply("Oi! 😄 Diz algo para eu responder!")
        else:
            async with message.channel.typing():
                await asyncio.sleep(1.2)
                reply = await gerar_resposta(message.author.id, content)
                await message.reply(reply)

    elif message.reference and isinstance(message.reference.resolved, discord.Message):
        ref_msg = message.reference.resolved
        if ref_msg.author == bot.user:
            content = message.content.strip()
            if content:
                async with message.channel.typing():
                    await asyncio.sleep(1.2)
                    reply = await gerar_resposta(message.author.id, content)
                    await message.reply(reply)

    await bot.process_commands(message)


# =======================================================
# COMANDO !perguntar
# =======================================================
@bot.command()
async def perguntar(ctx, *, pergunta: str):
    await ctx.reply("✏️ A pensar...")
    async with ctx.channel.typing():
        await asyncio.sleep(1.2)
        resposta = await gerar_resposta(ctx.author.id, pergunta)
        await ctx.reply(resposta)


# =======================================================
# COMANDO !bloquear <canal>
# =======================================================
@bot.command()
@commands.has_permissions(manage_channels=True)
async def bloquear(ctx, canal: discord.TextChannel = None):
    canal = canal or ctx.channel
    overwrite = canal.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = False
    await canal.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.reply(f"🔒 Canal {canal.mention} bloqueado: só leitura para membros.")


# =======================================================
# COMANDO !desbloquear <canal>
# =======================================================
@bot.command()
@commands.has_permissions(manage_channels=True)
async def desbloquear(ctx, canal: discord.TextChannel = None):
    canal = canal or ctx.channel
    overwrite = canal.overwrites_for(ctx.guild.default_role)
    overwrite.send_messages = True
    await canal.set_permissions(ctx.guild.default_role, overwrite=overwrite)
    await ctx.reply(f"🔓 Canal {canal.mention} desbloqueado: membros podem enviar mensagens.")


# =======================================================
# INICIAR BOT
# =======================================================
bot.run(DISCORD_TOKEN)
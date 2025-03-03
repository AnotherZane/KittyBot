import os
import logging
import db
import sqlite3
import hikari
import lightbulb
from PIL import Image
import requests
from commons.agents import kitty_meme_agent
from typing import Final
from pydantic_ai import BinaryContent



plugin = lightbulb.Plugin("MemeRater")


MEME_CHANNEL_ID = int(os.environ.get("MEME_CHANNEL_ID", 0))
MEME_RATE_PROMPT: Final[str] = os.environ.get("MEME_RATING_PROMPT",
    "Rate this meme out of 10, with 10 being the funniest. Rate is solely on how funny a bunch of computer science nerds would find it. ONLY Return an integer."
)
MINIMUM_MEME_RATING_TO_NOT_DELETE: Final[int] = int(os.environ.get("MEME_QUALITY_THRESHOLD", "6"))
DELETE_SHIT: Final[bool] = False
IMG_FILE_EXTENSIONS: Final = {"jpg", "jpeg", "png", "webp"}



async def get_meme_rating(image_url: str, user: str, att_ext: str):
    image = requests.get(image_url, stream=True)
    if not image.raw:
        logging.info("Not image")
        return ''
    response = await kitty_meme_agent.run(image=image, user=user)
    logging.info(f'Meme rating response: {response}')
    return response

def number_emoji(number: int):
    if number == 10:
        unicode = "\N{KEYCAP TEN}"
    else:
        unicode = f"{number}\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}"
    return hikari.UnicodeEmoji.parse(unicode)

@plugin.listener(hikari.GuildMessageCreateEvent)
async def main(event: hikari.GuildMessageCreateEvent) -> None:
    if event.channel_id != MEME_CHANNEL_ID:
        return
    cursor = db.cursor()
    ratings = []
    
    for attachment in event.message.attachments:
        att_ext = attachment.extension
        logging.info(f"Attachment extension: {att_ext}")
        if att_ext not in IMG_FILE_EXTENSIONS:
            continue
        image_url = attachment.url
        try:
            rating = await get_meme_rating(image_url, event.author.username, att_ext)
            ratings.append(int(rating))
        except Exception as e:
            continue
    if not ratings:
        return

    avg_rating = min(max(0, sum(ratings) // len(ratings)), 10)

    await event.message.add_reaction(emoji=number_emoji(avg_rating))
    await event.message.add_reaction(emoji="🐱")

    if avg_rating >= MINIMUM_MEME_RATING_TO_NOT_DELETE:
        await event.message.add_reaction(emoji="👍")
    elif DELETE_SHIT:
        await event.message.delete()
        await event.message.respond(
            f"That meme was garbage 💩💩💩. I rated it {avg_rating}/10. Send something better."
        )
    else:
        await event.message.add_reaction(emoji="💩")

    # add some basic meme stats to the db so we can track who is improving, rotting, or standing still
    # avg rating row inserted is just for this set of memes. Another query elsewhere aggregates.
    cursor.execute(
        "insert into meme_stats values(?, ?, ?, ?)",
        (event.author_id, event.message_id, avg_rating, event.message.timestamp),
    )
    db.commit()



def load(bot: lightbulb.BotApp) -> None:
    bot.add_plugin(plugin)

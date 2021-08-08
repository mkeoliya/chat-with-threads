import logging
from datetime import timedelta
from collections import deque
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext, MessageHandler, Filters
from telegram.error import BadRequest, TelegramError
from mwt import MWT

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

class Config:
    TOKEN = 'TOKEN' # replace with bot token from @BotFather
    CHANNEL_NAME = '@channel'
    ADMIN_TIMER = 600  # in seconds
    CACHE_TIMEOUT = 1 # in seconds

class PostButton:
    data = 'P'
    reply_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Post", callback_data=data)],
    ])

class Messages:
    previous_bot_message = None

@MWT(timeout=1)
def get_admin_ids(bot, chat_id):
    """Returns a list of admin IDs for a given chat. Results are cached for 1 hour."""
    return [admin.user.id for admin in bot.get_chat_administrators(chat_id)]

def callback_remove_admin(context: CallbackContext):
    args = context.job.context
    # if all permissions are set to False, a chat member is demoted to admin
    context.bot.promote_chat_member(
        chat_id=args['chat_id'],
        user_id=args['user_id'],
        can_change_info=False,
        can_post_messages=False,
        can_edit_messages=False,
        can_delete_messages=False,
        can_invite_users=False,
        can_restrict_members=False,
        can_pin_messages=False,
        can_promote_members=False,
        can_manage_chat=False,
        can_manage_voice_chats=False
    )

def handle_post(query, update: Update, context: CallbackContext):
    user_id = query.from_user.id
    chat_id = Config.CHANNEL_NAME

    # if the user is already an admin (temporary or otherwise), ignore the button click
    if user_id in get_admin_ids(context.bot, chat_id):
        return

    try:
        context.bot.promote_chat_member(
            chat_id=Config.CHANNEL_NAME,
            user_id=user_id,
            can_post_messages=True
        )
    except BadRequest:
        pass

    context.job_queue.run_once(callback_remove_admin,
                               when=timedelta(seconds=Config.ADMIN_TIMER), 
                               context={
                                   'chat_id': chat_id,
                                   'user_id': user_id,
                               }
                            )
def button(update: Update, context: CallbackContext) -> None:
    """Parses the CallbackQuery and updates the message text."""
    query = update.callback_query
    handle_post(query, update, context)

    # CallbackQueries need to be answered, even if no notification to the user is needed
    # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
    query.answer()


def new_message(update: Update, context: CallbackContext):
    if update.edited_channel_post:
        return
    
    update.effective_message.copy(chat_id=Config.CHANNEL_NAME)
    update.effective_message.delete()


    context.bot.send_message(
        text='\n',
        reply_markup=PostButton.reply_markup,
        chat_id=Config.CHANNEL_NAME,
        disable_notification=True,
        )

def new_forwarded_message(update: Update, context: CallbackContext):
    if update.edited_channel_post:
        return
    
    message = update.effective_message
    print(message)
    from_chat_id = message.forward_from.id
    message.forward(
        chat_id=Config.CHANNEL_NAME,
        from_chat_id=from_chat_id,
        message_id=message.message_id
        )
    message.delete()


    context.bot.send_message(
        text='\n',
        reply_markup=PostButton.reply_markup,
        chat_id=Config.CHANNEL_NAME,
        disable_notification=True,
        )

def main() -> None:
    """Run the bot."""
    # Create the Updater and pass it your bot's token.
    updater = Updater(Config.TOKEN)
    updater.dispatcher.add_handler(MessageHandler(Filters.all & (~ Filters.forwarded), new_message))
    updater.dispatcher.add_handler(MessageHandler(Filters.forwarded, new_forwarded_message))
    updater.dispatcher.add_handler(CallbackQueryHandler(button))

    # Start the Bot
    updater.start_polling()

    # Run the bot until the user presses Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT
    updater.idle()


if __name__ == '__main__':
    main()
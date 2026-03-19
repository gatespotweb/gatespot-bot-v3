import os
import json
import logging
import datetime
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

logging.basicConfig(level=logging.INFO)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEBAPP_URL = os.environ.get("WEBAPP_URL", "")

TYPE, APPARTEMENT, CATEGORIE, CLIENT, NUITS, DESCRIPTION, MONTANT = range(7)

APPARTEMENTS = {
    "Casablanca": ["Anfa City", "Anfa 212", "Tour 33", "Gauthier"],
    "Rabat": ["Souissi", "Agdal"]
}

VILLES = {
    "Anfa City": "Casablanca",
    "Anfa 212": "Casablanca",
    "Tour 33": "Casablanca",
    "Gauthier": "Casablanca",
    "Souissi": "Rabat",
    "Agdal": "Rabat"
}

CATEGORIES_DEPENSE = ["Maintenance", "Electricite", "Eau", "Consommables", "Menage", "Autre"]

user_data_store = {}


def envoyer_vers_sheets(payload):
    if not WEBAPP_URL:
        return "URL Web App non configuree"
    try:
        resp = requests.get(WEBAPP_URL, params=payload, timeout=30)
        if resp.status_code == 200:
            return "Enregistre dans Google Sheets !"
        else:
            return "Erreur: " + str(resp.status_code)
    except Exception as e:
        logging.error("Erreur envoi Sheets: " + str(e))
        return "Erreur d'envoi: " + str(e)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Depense", callback_data="type_depense"),
         InlineKeyboardButton("Revenu", callback_data="type_revenu")]
    ]
    await update.message.reply_text(
        "Gatespot Bot\n\nQue veux-tu enregistrer ?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TYPE


async def type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data_store[user_id] = {"type": query.data.replace("type_", "")}

    keyboard = []
    for ville, apparts in APPARTEMENTS.items():
        keyboard.append([InlineKeyboardButton("--- " + ville + " ---", callback_data="ville_" + ville)])
        row = []
        for appart in apparts:
            row.append(InlineKeyboardButton(appart, callback_data="appart_" + appart))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)

    type_label = "depense" if user_data_store[user_id]["type"] == "depense" else "revenu"
    await query.edit_message_text(
        type_label.capitalize() + " - Quel appartement ?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return APPARTEMENT


async def appartement_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("ville_"):
        return APPARTEMENT
    user_id = query.from_user.id
    appart = query.data.replace("appart_", "")
    user_data_store[user_id]["appartement"] = appart
    user_data_store[user_id]["ville"] = VILLES[appart]
    type_op = user_data_store[user_id]["type"]
    if type_op == "depense":
        keyboard = []
        row = []
        for cat in CATEGORIES_DEPENSE:
            row.append(InlineKeyboardButton(cat, callback_data="cat_" + cat))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        await query.edit_message_text(appart + " - Categorie ?", reply_markup=InlineKeyboardMarkup(keyboard))
        return CATEGORIE
    else:
        user_data_store[user_id]["categorie"] = "Cash"
        await query.edit_message_text(appart + " - Revenu Cash\n\nNom du client ?")
        return CLIENT


async def categorie_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data_store[user_id]["categorie"] = query.data.replace("cat_", "")
    appart = user_data_store[user_id]["appartement"]
    cat = user_data_store[user_id]["categorie"]
    await query.edit_message_text(appart + " - " + cat + "\n\nDecris en quelques mots :\n(ex: reparation clim, capsules cafe...)")
    return DESCRIPTION


async def client_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_data_store[user_id]["client"] = update.message.text.strip()
    appart = user_data_store[user_id]["appartement"]
    client = user_data_store[user_id]["client"]
    await update.message.reply_text(appart + " - " + client + "\n\nCombien de nuits ?")
    return NUITS


async def nuits_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    nuits_text = update.message.text.strip()
    if not nuits_text.isdigit():
        await update.message.reply_text("Nombre invalide ! Tape un nombre (ex: 3)")
        return NUITS
    user_data_store[user_id]["nuits"] = int(nuits_text)
    appart = user_data_store[user_id]["appartement"]
    client = user_data_store[user_id]["client"]
    nuits = user_data_store[user_id]["nuits"]
    await update.message.reply_text(appart + " - " + client + " - " + str(nuits) + " nuits\n\nMontant total en DH ?")
    return MONTANT


async def description_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_data_store[user_id]["description"] = update.message.text.strip()
    appart = user_data_store[user_id]["appartement"]
    cat = user_data_store[user_id]["categorie"]
    desc = user_data_store[user_id]["description"]
    await update.message.reply_text(appart + " - " + cat + " - " + desc + "\n\nMontant en DH ?")
    return MONTANT


async def montant_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    montant = update.message.text.strip().replace(",", ".")
    if not montant.replace(".", "").isdigit():
        await update.message.reply_text("Montant invalide ! Tape un nombre (ex: 500)")
        return MONTANT
    user_data_store[user_id]["montant"] = montant
    return await enregistrer(update, user_id)


async def enregistrer(update, user_id):
    data = user_data_store.get(user_id, {})
    type_op = data.get("type")
    if type_op == "revenu":
        payload = {
            "type": "revenu",
            "date": str(datetime.date.today()),
            "appartement": data.get("appartement"),
            "ville": data.get("ville"),
            "client": data.get("client", ""),
            "nuits": data.get("nuits", ""),
            "montant": data.get("montant"),
            "menage": "0",
            "notes": "Revenu Cash"
        }
    else:
        payload = {
            "type": "depense",
            "date": str(datetime.date.today()),
            "appartement": data.get("appartement"),
            "ville": data.get("ville"),
            "categorie": data.get("categorie"),
            "montant": data.get("montant"),
            "notes": data.get("description", "")
        }
    status = envoyer_vers_sheets(payload)
    if type_op == "revenu":
        message = (
            "Revenu enregistre !\n\n"
            "Appartement: " + str(data.get("appartement")) + " (" + str(data.get("ville")) + ")\n"
            "Client: " + str(data.get("client")) + "\n"
            "Nuits: " + str(data.get("nuits")) + "\n"
            "Montant: " + str(data.get("montant")) + " DH\n\n"
            + status
        )
    else:
        message = (
            "Depense enregistree !\n\n"
            "Appartement: " + str(data.get("appartement")) + " (" + str(data.get("ville")) + ")\n"
            "Categorie: " + str(data.get("categorie")) + "\n"
            "Description: " + str(data.get("description", "")) + "\n"
            "Montant: " + str(data.get("montant")) + " DH\n\n"
            + status
        )
    keyboard = [[InlineKeyboardButton("Nouvelle saisie", callback_data="restart")]]
    await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    user_data_store.pop(user_id, None)
    return ConversationHandler.END


async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("Depense", callback_data="type_depense"),
         InlineKeyboardButton("Revenu", callback_data="type_revenu")]
    ]
    await query.edit_message_text("Gatespot Bot\n\nQue veux-tu enregistrer ?", reply_markup=InlineKeyboardMarkup(keyboard))
    return TYPE


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Annule. Tape /start pour recommencer.")
    return ConversationHandler.END


def main():
    app = Application.builder().token(TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start), CallbackQueryHandler(restart, pattern="^restart$")],
        states={
            TYPE: [CallbackQueryHandler(type_handler, pattern="^type_")],
            APPARTEMENT: [CallbackQueryHandler(appartement_handler, pattern="^appart_"), CallbackQueryHandler(appartement_handler, pattern="^ville_")],
            CATEGORIE: [CallbackQueryHandler(categorie_handler, pattern="^cat_")],
            CLIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, client_handler)],
            NUITS: [MessageHandler(filters.TEXT & ~filters.COMMAND, nuits_handler)],
            DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, description_handler)],
            MONTANT: [MessageHandler(filters.TEXT & ~filters.COMMAND, montant_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False
    )
    app.add_handler(conv_handler)
    print("Gatespot Bot v3 demarre !")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler
)

# Configuración básica
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados para la conversación de /cerrar
SELECTING_TASK, SUCCESS, COMMENT, CONFIRM_COMMENT = range(4)

# Estructuras de datos para almacenar tareas
open_tasks = {}
closed_tasks = {}
task_counter = 1  # Contador global

# ----- Comandos del Bot -----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "¡Bienvenido al Control de Actividades Nocturnas!\n"
        "Usa /auto, /task, /cerrar o /reporte para gestionar tareas."
    )

async def auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Pega aquí el mensaje de actividades:")
    return "AUTO_TASK"

async def handle_auto_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global task_counter
    text = update.message.text
    
    # Extraer tareas del mensaje (líneas que comienzan con número y guión)
    tasks = []
    for line in text.split('\n'):
        line = line.strip()
        if any(line.startswith(f"{i}-") for i in range(1, 10)):
            tasks.append(line)
    
    if not tasks:
        await update.message.reply_text("❌ No se detectaron tareas en el formato esperado (ej: '1- Descripción').")
        return ConversationHandler.END
    
    # Guardar tareas con números consecutivos
    for task in tasks:
        task_text = task.split("-", 1)[1].strip()  # Elimina el número original
        open_tasks[task_counter] = task_text
        task_counter += 1
    
    await update.message.reply_text(f"✅ Se agregaron {len(tasks)} tareas automáticamente.")
    return ConversationHandler.END

async def task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ingresa una tarea manualmente:")
    return "MANUAL_TASK"

async def handle_manual_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global task_counter
    task_text = update.message.text
    open_tasks[task_counter] = task_text
    await update.message.reply_text(f"✅ Tarea {task_counter} agregada: {task_text}")
    task_counter += 1
    return ConversationHandler.END

async def cerrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not open_tasks:
        await update.message.reply_text("⚠️ No hay tareas abiertas para cerrar.")
        return ConversationHandler.END
    
    # Mostrar tareas abiertas numeradas
    tasks_list = "\n".join([f"{num}. {task}" for num, task in open_tasks.items()])
    await update.message.reply_text(
        f"Tareas abiertas:\n{tasks_list}\n\n¿Cuál tarea debes cerrar? (Responde con el número):"
    )
    return SELECTING_TASK

async def select_task_to_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        task_num = int(update.message.text)
        if task_num not in open_tasks:
            await update.message.reply_text("❌ Número de tarea inválido. Intenta de nuevo.")
            return SELECTING_TASK
        
        context.user_data["selected_task"] = task_num
        keyboard = [
            [InlineKeyboardButton("Sí", callback_data="yes")],
            [InlineKeyboardButton("No", callback_data="no")]
        ]
        await update.message.reply_text(
            "¿Esta tarea fue realizada con éxito?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SUCCESS
    except ValueError:
        await update.message.reply_text("❌ Por favor, ingresa solo el número de la tarea.")
        return SELECTING_TASK

async def ask_for_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    success = query.data == "yes"
    context.user_data["success"] = success
    
    keyboard = [
        [InlineKeyboardButton("Sí", callback_data="yes")],
        [InlineKeyboardButton("No", callback_data="no")]
    ]
    await query.edit_message_text(
        "¿Quieres agregar un comentario?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return COMMENT

async def handle_comment_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "yes":
        await query.edit_message_text("Escribe aquí tu comentario:")
        return CONFIRM_COMMENT
    else:
        # Cierra la tarea sin comentario
        task_num = context.user_data["selected_task"]
        success = context.user_data["success"]
        task_text = open_tasks.pop(task_num)
        status_emoji = "✅" if success else "❌"
        closed_task_text = f"{status_emoji} {task_text}"
        closed_tasks[task_num] = closed_task_text
        
        await query.edit_message_text(f"Tarea {task_num} cerrada: {closed_task_text}")
        return ConversationHandler.END

async def close_task_with_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    task_num = context.user_data["selected_task"]
    success = context.user_data["success"]
    comment = update.message.text
    task_text = open_tasks.pop(task_num)
    
    status_emoji = "✅" if success else "❌"
    closed_task_text = f"{status_emoji} {task_text} ({comment})"
    closed_tasks[task_num] = closed_task_text
    
    await update.message.reply_text(f"Tarea {task_num} cerrada: {closed_task_text}")
    return ConversationHandler.END

async def reporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global task_counter, open_tasks, closed_tasks
    
    # Cerrar todas las tareas abiertas como pendientes
    for task_num, task_text in open_tasks.items():
        closed_tasks[task_num] = f"❌ {task_text} (Queda pendiente)"
    open_tasks.clear()
    
    # Generar reporte
    if not closed_tasks:
        report = "⚠️ No hay actividades registradas en este turno."
    else:
        report = "Buen día. Terminando el turno, este es el reporte de actividades planeadas:\n" + \
                 "\n".join([f"{num}. {task}" for num, task in sorted(closed_tasks.items())]) + \
                 "\n¡Gracias y buen turno!"
    
    await update.message.reply_text(report)
    
    # Reiniciar sistema
    closed_tasks.clear()
    task_counter = 1
    return ConversationHandler.END

# ----- Main -----
def main():
    application = ApplicationBuilder().token("7677028042:AAG8BxbT-lYFjSx5wRowbzf0PQ8TJ6jMKm0").build()
    
    # Handlers
    conv_handler_auto = ConversationHandler(
        entry_points=[CommandHandler("auto", auto)],
        states={
            "AUTO_TASK": [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_auto_task)],
        },
        fallbacks=[],
    )
    
    conv_handler_task = ConversationHandler(
        entry_points=[CommandHandler("task", task)],
        states={
            "MANUAL_TASK": [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_task)],
        },
        fallbacks=[],
    )
    
    conv_handler_cerrar = ConversationHandler(
        entry_points=[CommandHandler("cerrar", cerrar)],
        states={
            SELECTING_TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_task_to_close)],
            SUCCESS: [CallbackQueryHandler(ask_for_comment)],
            COMMENT: [CallbackQueryHandler(handle_comment_decision)],
            CONFIRM_COMMENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, close_task_with_comment)],
        },
        fallbacks=[],
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(conv_handler_auto)
    application.add_handler(conv_handler_task)
    application.add_handler(conv_handler_cerrar)
    application.add_handler(CommandHandler("reporte", reporte))
    
    application.run_polling()

if __name__ == "__main__":
     application.run_polling()
    main()

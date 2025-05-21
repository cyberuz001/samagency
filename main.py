async def proceed_to_payment(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    service = data.get("service", "")
    details = data.get("details", "")
    colors = data.get("colors", "")
    complexity = data.get("complexity", "")
    base_price = data.get("base_price", 100_000)
    promo_code = data.get("promo_code", None)
    promo_discount = data.get("promo_discount", 0)
    referral_discount = 0.05 if user_id % 2 == 0 else 0
    total_discount = promo_discount + referral_discount
    total_price = int(base_price * (1 - total_discount))
    timestamp = int(time.time())

    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO orders (user_id, service, details, colors, complexity, promo_code, promo_discount, referral_discount, total_price, timestamp, status, payment_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'pending')
            """, (user_id, service, details, colors, complexity, promo_code, promo_discount, referral_discount, total_price, timestamp))
            order_id = c.lastrowid
            conn.commit()
    except Exception as e:
        logger.error(f"Database error: {e}")
        await message.answer("Xatolik yuz berdi, iltimos qayta urinib ko‘ring.")
        return

    # ...qolgan kod o‘zgarishsiz...

with open("sleep_history.txt", "r", encoding="utf-8") as file:
    history = file.read()

print("История сна:")
print(history)

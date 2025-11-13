from pathlib import Path


filename = "example.txt"
extension = Path(filename).suffix
print(extension)  # Выводится расширение файла: «.txt»
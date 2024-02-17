from flask import Flask, request, send_file
from PIL import Image
from io import BytesIO, StringIO
import math, os, mimetypes
from werkzeug.utils import secure_filename
from colormath.color_objects import sRGBColor, LabColor
from colormath.color_conversions import convert_color

application = Flask(__name__)
application.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # Limit file size to 5MB

palette = {
    (0, 0, 0): '-',       # Black
    (255, 255, 255): ' ', # White
    (255, 255, 0): 'x'    # Yellow
}

rear_bed_palette = {
    (0, 0, 0): 'o',       # Black
    (255, 255, 255): ' ', # White
    (255, 255, 0): 'y'    # Yellow
}

ALLOWED_EXTENSIONS = {'png', 'gif', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def rgb_to_lab(rgb):
    rgb = sRGBColor(rgb[0], rgb[1], rgb[2], is_upscaled=True)
    lab = convert_color(rgb, LabColor)
    return lab

def color_distance(c1, c2):
    lab1 = rgb_to_lab(c1)
    lab2 = rgb_to_lab(c2)
    return math.sqrt((lab1.lab_l - lab2.lab_l) ** 2 + (lab1.lab_a - lab2.lab_a) ** 2 + (lab1.lab_b - lab2.lab_b) ** 2)

def closest_color(rgb):
    """Find the closest color in the palette to the given color."""
    return min(palette.keys(), key=lambda color: color_distance(color, rgb))

def image_to_txt(image_file, txt_file, duplicate_rows, add_empty_rows, empty_lines_increase, empty_lines_decrease):
    txt_lines = []
    with Image.open(image_file) as img:
        img = img.convert('RGB')

        for y in range(img.height):
            front_row = ''
            rear_row = ''
            for x in range(img.width):
                pixel = img.getpixel((x, y))
                closest = closest_color(pixel)
                front_row += palette[closest]
                if duplicate_rows:
                    rear_row += rear_bed_palette[closest]

            txt_lines.append(front_row)
            if duplicate_rows:
                txt_lines.append(rear_row)

    if add_empty_rows:
        txt_lines = add_empty_rows_if_needed(txt_lines, empty_lines_increase, empty_lines_decrease)

    for line in txt_lines:
        txt_file.write(line + '\n')

def add_empty_rows_if_needed(txt_lines, increase, decrease):
    result = []
    for i in range(len(txt_lines)):
        result.append(txt_lines[i])
        if i < len(txt_lines) - 1:
            current_count = txt_lines[i].count(' ')
            next_count = txt_lines[i + 1].count(' ')
            if current_count < next_count:
                for _ in range(increase):
                    result.append('$' * len(txt_lines[i]))
            elif current_count > next_count:
                for _ in range(decrease):
                    result.append('$' * len(txt_lines[i]))
    return result

@application.route('/')
def upload_form():
    return '''
        <!doctype html>
        <html>
        <head>
        <title>Upload Image</title>
        <style>
            body {
                padding: 20px;
                font-family: sans-serif;
                background: lightblue;
                text-align: center;
            }
            h1 {
                color: navy;
            }
            form {
                background: white;
                padding: 20px;
                border-radius: 8px;
                display: inline-block;
                text-align: left;
            }
            .form-group {
                margin-bottom: 10px;
            }
            .number-options {
                display: none;
                overflow: hidden;
            }
            label {
                display: inline-block;
                margin-bottom: 5px;
                font-weight: bold;
            }
            input[type="file"] {
                border: 1px solid #ddd;
                padding: 8px;
                border-radius: 4px;
            }
            input[type="checkbox"], input[type="number"] {
                margin-right: 10px;
            }
            input[type="number"] {
                width: 30px;
            }
            input[type="submit"] {
                background: navy;
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
            }
            input[type="submit"]:hover {
                background: darkblue;
            }
        </style>
        </head>
        <body>
        <h1>Convert bmp, png, gif to txt file</h1>
        <form method="post" enctype="multipart/form-data">
            <div class="form-group">
                <label>Select Image File (PNG, GIF, BMP):</label>
                <input type="file" name="file" accept=".png, .gif, .bmp">
            </div>
            <div class="form-group">
                <input type="checkbox" name="duplicate_rows" value="duplicate_rows" id="duplicate_rows">
                <label for="duplicate_rows">Duplicate rows to rear bed</label>
            </div>
            <div class="form-group">
                <input type="checkbox" name="add_empty_rows" value="add_empty_rows" id="add_empty_rows" onclick="toggleNumberOptions()">
                <label for="add_empty_rows">Add space for de-/increase edits</label>
            </div>
            <div class="number-options">
                <div class="form-group">
                    <label>Number of empty lines for increase edits:</label>
                    <input type="number" name="empty_lines_increase" value="1" min="0">
                </div>
                <div class="form-group">
                    <label>Number of empty lines for decrease edits:</label>
                    <input type="number" name="empty_lines_decrease" value="4" min="0">
                </div>
            </div>
            <div class="form-group">
                <input type="submit" value="Convert">
            </div>
        </form>

        <script>
            function toggleNumberOptions() {
                var checkBox = document.getElementById("add_empty_rows");
                var numberOptions = document.querySelector(".number-options");
                if (checkBox.checked) {
                    numberOptions.style.display = "block";
                    numberOptions.style.height = "auto";
                } else {
                    numberOptions.style.display = "none";
                    numberOptions.style.height = "0";
                }
            }
        </script>

        </body>
        </html>
        '''
@application.route('/', methods=['POST'])
def handle_upload():
    file = request.files['file']

    duplicate_rows = 'duplicate_rows' in request.form
    add_empty_rows = 'add_empty_rows' in request.form
    empty_lines_increase = int(request.form.get('empty_lines_increase', 1))
    empty_lines_decrease = int(request.form.get('empty_lines_decrease', 1))

    if file and allowed_file(file.filename):
        mime = mimetypes.guess_type(file.filename)[0]
        if not mime or not mime.startswith('image'):
            return "Invalid file type. Please upload an image.", 400

        filename = secure_filename(file.filename)
        txt_filename = os.path.splitext(filename)[0] + '.txt'

        with BytesIO() as in_memory_file:
            file.save(in_memory_file)
            in_memory_file.seek(0)

            txt_output = StringIO()
            image_to_txt(in_memory_file, txt_output, duplicate_rows, add_empty_rows, empty_lines_increase, empty_lines_decrease)
            txt_content = txt_output.getvalue()
            txt_output.close()

            output = BytesIO()
            output.write(txt_content.encode('utf-8'))
            output.seek(0)

            return send_file(
                output,
                as_attachment=True,
                download_name=txt_filename,
                mimetype='text/plain'
            )
    else:
        return "File type not allowed. Please upload PNG, GIF, or BMP files.", 400

if __name__ == "__main__":
    application.run()
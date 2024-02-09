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

def image_to_txt(image_file, txt_file, option):
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
                rear_row += rear_bed_palette[closest]

            txt_lines.append(front_row)
            if option == 'duplicate_rows':
                txt_lines.append(rear_row)

    if option == 'add_empty_rows':
        txt_lines = add_empty_rows_if_needed(txt_lines)

    for line in txt_lines:
        txt_file.write(line + '\n')

def add_empty_rows_if_needed(txt_lines):
    result = []
    for i in range(len(txt_lines)):
        result.append(txt_lines[i])
        if i < len(txt_lines) - 1:
            current_count = txt_lines[i].count(' ')
            next_count = txt_lines[i + 1].count(' ')
            if current_count != next_count:
                empty_line = '$' * len(txt_lines[i])
                result.extend([empty_line, empty_line])
    return result

@application.route('/')
def upload_form():
    return '''
        <!doctype html>
        <head>
        <title>Upload Image</title>
        <style>
            input:not([type="file"]), select { margin-left: 20px; }
        </style>
        </head>
        <body style="padding: 20px; font-family: sans-serif; background: lightblue">
        <h1>Convert bmp, png, gif to txt file</h1>
        <form method=post enctype=multipart/form-data>
          <input type="file" name="file" accept=".png, .gif, .bmp">
          <select name="option">
            <option value="none">No additional option</option>
            <option value="duplicate_rows">Duplicate rows to rear bed</option>
            <option value="add_empty_rows">Add space for de-/increase edits</option>
          </select>
          <input type="submit" value="Convert">
        </form>
        </body>
        '''

@application.route('/', methods=['POST'])
def handle_upload():
    file = request.files['file']
    option = request.form.get('option', 'none')

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
            image_to_txt(in_memory_file, txt_output, option)
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
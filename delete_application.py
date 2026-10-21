
import json
from pathlib import Path
import sys
import requests
from bs4 import BeautifulSoup
from urllib.parse import parse_qsl
from config import get_json_path
import argparse

HERE = Path(__file__).resolve().parent
JSON_FILE = get_json_path("personal.json")
BASE_URL = "https://onlineservices.immigration.govt.nz"

DELETE_PATH = "/WorkingHoliday/Application/Delete.aspx"

if getattr(sys, "frozen", False):
    HERE = Path(sys.executable).resolve().parent
else:
    HERE = Path(__file__).resolve().parent

NEXT_BUTTON = (
    "_ctl0:ContentPlaceHolder1:"
    "wizardPageFooter:wizardPageNavigator:nextImageButton"
)


def load_cookies(session, filename="cookies.txt"):
    cookie_text = Path(filename).read_text(
        encoding="utf-8"
    ).strip()

    if cookie_text.lower().startswith("cookie:"):
        cookie_text = cookie_text.split(":", 1)[1].strip()

    session.headers["Cookie"] = cookie_text


def load_personal_data(filename=JSON_FILE):
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("personal.json must contain a JSON object")

    return data

def delete_file():
    parser = argparse.ArgumentParser(description='Clear local files after official application deletion')
    parser.add_argument('--dir', type=Path, default=HERE, help='Directory containing id.txt and progress.json')
    args = parser.parse_args()
    root = args.dir.resolve()
    id_file = root / 'id.txt'
    progress_file = root / 'progress.json'
    if not id_file.is_file():
        raise SystemExit(f'Cannot find {id_file}; no files deleted.')
    application_id = id_file.read_text(encoding='utf-8-sig').strip()
    if not application_id.isdigit():
        raise SystemExit('Invalid id.txt; no files deleted.')
    if progress_file.is_file():
        try:
            state = json.loads(progress_file.read_text(encoding='utf-8'))
            state_id = state.get('application_id')
            if state_id is not None and str(state_id) != application_id:
                raise SystemExit('progress.json refers to a different application; no files deleted.')
        except json.JSONDecodeError:
            raise SystemExit('progress.json is invalid JSON; no files deleted.')
    print(f'Application ID: {application_id}')
    print('Delete this application through the official Immigration NZ website first.')
    # answer = input(f'After confirming deletion on the website, type DELETE {application_id}: ').strip()
    # if answer != f'DELETE {application_id}':
    #     raise SystemExit('Cancelled; no local files deleted.')
    for path in (id_file, progress_file):
        if path.is_file():
            path.unlink()
            print(f'Deleted local file: {path.name}')
    print('Local cleanup complete. This script did not delete the online application.')

def run(session, application_id, submit=False):
    url = BASE_URL + DELETE_PATH + "?ApplicationId=" + str(application_id)

    params = {
        "ApplicationId": str(application_id),
        "IndividualType": "Primary",
        "IndividualIndex": "1",
        "StatusChanged": "False",
    }

    response = session.get(
        url,
        params=params,
        timeout=30
    )

    body = {}

    required_fields = [
        "__VIEWSTATE",
        "__VIEWSTATEGENERATOR",
        "__EVENTVALIDATION",
    ]


    protected_fields = {
        "__VIEWSTATE",
        "__VIEWSTATEGENERATOR",
        "__EVENTVALIDATION",
    }

    # 4. Các giá trị từ request mẫu
    body["__VIEWSTATE"]="WnQG/dmhOtGHkW6YSYvz8fMisQLOKAvLFKQ87X4S6Qz0ufhhe4A0hNgB2ZBvKCrxp6QTHmnSYVuJISL9TC3KSQQFJ5TtHWbVR4Tn5FT55eDZR75fUVVSVqGjjuy4zhuRtm4icdOc7iNx6L6JPAjEff7vZU9kLmeQU4U4ETMG+OVnmf8y"
    body["__VIEWSTATEGENERATOR"]="334984A9"
    body["__EVENTVALIDATION"]="YqTU+pouTzA29FJ9czYtJQHCyJvCF9gfWQIWsJuax1k8OsZV4QCerdP+X1zV8qjZKH+QsfRPN7N5czlpSclWC2N0s+kzK7R7w6PSNwpF5ZQ4LaAlXOEnle9JPGwe/e1U3Aek6TR1SylYEdYI4hTbpQpmkg8="
    body["__SCROLLPOSITIONX"] = "0"
    body["__SCROLLPOSITIONY"] = "104"
    body["__EVENTTARGET"] = ""
    body["__EVENTARGUMENT"] = ""

    body["_ctl0:ContentPlaceHolder1:okDeleteButton"] = "YES, DELETE"
    body["_ctl0:ClientScrollHeight"] = "10"

    print("Body:", body)

    prepared = requests.Request(
        method="POST",
        url=url,
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": response.url,
        }
    )

    prepared = session.prepare_request(prepared)

    print("=" * 60)
    print("STEP 1A")
    print("=" * 60)
    print("Method:", prepared.method)
    print("URL:", prepared.url)
    print("Body parameters:", len(body))
    print("Body size:", len(prepared.body or b""))

    if not submit:
        print("Preview only. POST not sent.")
        return None

    result = session.send(
        prepared,
        timeout=30,
        allow_redirects=True
    )

    print("\n=== RESPONSE ===")
    print("Status:", result.status_code)
    print("Final URL:", result.url)

    Path("delete_response.html").write_text(
        result.text,
        encoding="utf-8"
    )

    print("URL: ",url)

    print("\n========== RAW POST BODY ==========")

    raw_body = prepared.body

    if isinstance(raw_body, bytes):
        raw_body = raw_body.decode("utf-8")

    print(raw_body)

    print("\n========== DECODED BODY ==========")

    for key, value in parse_qsl(raw_body, keep_blank_values=True):
        if key in ("__VIEWSTATE", "__EVENTVALIDATION"):
            print(f"{key} = [hidden, {len(value)} characters]")
        else:
            print(f"{key} = {value}")

    print("==================================\n")

    Path("delete_body.txt").write_text(raw_body,encoding="utf-8")

    print("Saved POST body to delete_body.txt")

    print("Response saved to delete_response.html")
    print("The application has been successfully deleted" in result.text)
    if("The application has been successfully deleted" in result.text):
        print("Application deleted successfully.")
        delete_file()
    return result

def main():
    session = requests.Session()

    load_cookies(session, "cookies.txt")

    application_id = Path("id.txt").read_text(
        encoding="utf-8"
    ).strip()

    if not application_id.isdigit():
        raise ValueError("Invalid ApplicationId")

    run(
        session=session,
        application_id=application_id,
        submit=True
    )




if __name__ == "__main__":
    main()

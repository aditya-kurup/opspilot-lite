import argparse
from app import audit

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--request-id', required=True)
    request = audit.get_request(parser.parse_args().request_id)
    if not request or request.get('status') not in {'executing', 'provisioned'}:
        raise SystemExit('request is missing or not approved')
    print('approved request validated')

if __name__ == '__main__':
    main()

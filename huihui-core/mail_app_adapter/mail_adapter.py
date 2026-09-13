#!/usr/bin/env python3
"""
macOS Mail Adapter — Read emails from Apple Mail.app without OAuth

Uses osascript to script the Mail.app, extracting recent messages.
No Google OAuth required — uses local Mail.app data directly.

Core responsibilities:
1. Extract recent emails from Mail.app inbox
2. Parse sender, subject, body, date
3. Feed important emails to memory tree
4. Support for multiple mailboxes (Inbox, Sent, etc.)

Usage:
    python3 mail_adapter.py fetch            # fetch recent inbox emails
    python3 mail_adapter.py search "keyword" # search emails by keyword
    python3 mail_adapter.py inbox --limit 20 # get last 20 inbox emails
    python3 mail_adapter.py status           # show mailbox status
"""

import subprocess
import re
import json
from datetime import datetime, timezone
from typing import Optional, TypedDict

# ─── Configuration ────────────────────────────────────────────────────────────

MAX_EMAIL_AGE_DAYS = 7  # Only fetch emails from last 7 days by default
MAX_BODY_CHARS = 2000   # Truncate body to this length
MEMORY_TREE_CLI = None  # Will be set from __init__

# ─── Data Types ───────────────────────────────────────────────────────────────

class Email(TypedDict):
    id: str
    subject: str
    sender: str
    recipient: str
    date: str
    body: str
    is_read: bool
    is_flagged: bool
    mailbox: str

# ─── AppleScript Interface ────────────────────────────────────────────────────

def run_applescript(script: str) -> str:
    """Execute AppleScript and return output"""
    try:
        result = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"osascript error: {result.stderr}")
        return result.stdout
    except FileNotFoundError:
        raise RuntimeError("osascript not available (macOS only)")
    except Exception as e:
        raise RuntimeError(f"Failed to run AppleScript: {e}")

def escape_for_applescript(text: str) -> str:
    """Escape text for safe use in AppleScript string"""
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

def get_mailboxes() -> list[str]:
    """List all mailboxes in Mail.app"""
    script = '''
    tell application "Mail"
        set mailboxList to {}
        repeat with aMailbox in mailboxes
            set mailboxName to name of aMailbox
            if mailboxName is not "" then
                set end of mailboxList to mailboxName
            end if
        end repeat
        return mailboxList
    end tell
    '''
    
    result = run_applescript(script)
    mailboxes = [m.strip() for m in result.strip().split(',')]
    return [m for m in mailboxes if m]

def get_recent_emails(mailbox: str = "INBOX", limit: int = 20, 
                      max_age_days: int = MAX_EMAIL_AGE_DAYS) -> list[Email]:
    """
    Get recent emails from specified mailbox.
    Uses AppleScript to read from Mail.app directly.
    """
    
    escaped_mailbox = escape_for_applescript(mailbox)
    
    script = f'''
    tell application "Mail"
        set theMailbox to mailbox "{escaped_mailbox}"
        set theMessages to (every message of theMailbox whose read status is true or read status is false)
        
        set emailList to {{}}
        set cnt to 0
        
        repeat with aMessage in theMessages
            set cnt to cnt + 1
            if cnt > {limit} then exit repeat
            
            set msgSubject to subject of aMessage
            set msgSender to sender of aMessage
            set msgRecipient to (display name of recipients of aMessage as string)
            set msgDate to date received of aMessage
            set msgBody to content of aMessage
            set msgRead to read status of aMessage
            set msgFlagged to flagged status of aMessage
            set msgID to id of aMessage
            
            -- Format date as ISO string
            set dateStr to (year of msgDate as string) & "-" & _
                (text -2 of ("0" & (month of msgDate as integer) as string)) & "-" & _
                (text -2 of ("0" & (day of msgDate as string) as string)) & "T" & _
                (text -2 of ("0" & (hours of msgDate as integer) as string)) & ":" & _
                (text -2 of ("0" & (minutes of msgDate as integer) as string)) & ":" & _
                (text -2 of ("0" & (seconds of msgDate as integer) as string))
            
            -- Build dict entry (AppleScript records don't support complex structures well)
            set entry to msgID as string & "|||"
            set entry to entry & msgSubject & "|||"
            set entry to entry & msgSender & "|||"
            set entry to entry & msgRecipient & "|||"
            set entry to entry & dateStr & "|||"
            set entry to entry & ((msgRead as integer) as string) & "|||"
            set entry to entry & ((msgFlagged as integer) as string) & "|||"
            
            -- Truncate body to 2000 chars for AppleScript safety
            if (length of msgBody) > {MAX_BODY_CHARS} then
                set msgBody to (text 1 thru {MAX_BODY_CHARS} of msgBody)
            end if
            
            set entry to entry & msgBody
            
            set end of emailList to entry
        end repeat
        
        return emailList
    end tell
    '''
    
    try:
        result = run_applescript(script)
    except Exception as e:
        print(f"AppleScript error: {e}")
        return []
    
    emails = []
    for line in result.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        
        parts = line.split('|||')
        if len(parts) < 7:
            continue
        
        try:
            email = Email(
                id=parts[0],
                subject=parts[1],
                sender=parts[2],
                recipient=parts[3],
                date=parts[4],
                is_read=parts[5] == '1',
                is_flagged=parts[6] == '1',
                body=parts[7] if len(parts) > 7 else '',
                mailbox=mailbox
            )
            emails.append(email)
        except:
            continue
    
    return emails

def search_emails(keyword: str, mailbox: str = "INBOX", limit: int = 20) -> list[Email]:
    """
    Search emails by keyword using AppleScript.
    """
    
    escaped_keyword = escape_for_applescript(keyword)
    escaped_mailbox = escape_for_applescript(mailbox)
    
    script = f'''
    tell application "Mail"
        set theMailbox to mailbox "{escaped_mailbox}"
        set theMessages to (every message of theMailbox whose subject contains "{escaped_keyword}" or content contains "{escaped_keyword}")
        
        set emailList to {{}}
        set cnt to 0
        
        repeat with aMessage in theMessages
            set cnt to cnt + 1
            if cnt > {limit} then exit repeat
            
            set msgSubject to subject of aMessage
            set msgSender to sender of aMessage
            set msgDate to date received of aMessage
            set msgBody to content of aMessage
            set msgRead to read status of aMessage
            set msgID to id of aMessage
            
            set dateStr to (year of msgDate as string) & "-" & _
                (text -2 of ("0" & (month of msgDate as integer) as string)) & "-" & _
                (text -2 of ("0" & (day of msgDate as string) as string))
            
            set entry to msgID as string & "|||" & msgSubject & "|||" & msgSender & "|||" & dateStr & "|||" & ((msgRead as integer) as string) & "|||" & msgBody
            
            set end of emailList to entry
        end repeat
        
        return emailList
    end tell
    '''
    
    try:
        result = run_applescript(script)
    except Exception as e:
        print(f"Search error: {e}")
        return []
    
    emails = []
    for line in result.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
        
        parts = line.split('|||')
        if len(parts) < 5:
            continue
        
        try:
            email = Email(
                id=parts[0],
                subject=parts[1],
                sender=parts[2],
                date=parts[3],
                is_read=parts[4] == '1',
                is_flagged=False,
                body=parts[5] if len(parts) > 5 else '',
                recipient='',
                mailbox=mailbox
            )
            emails.append(email)
        except:
            continue
    
    return emails

def email_to_memory(email: Email) -> str:
    """Format an email as a memory tree compatible string"""
    body = email['body'][:MAX_BODY_CHARS].strip()
    
    memory = f"""## 邮件: {email['subject']}

**发件人:** {email['sender']}
**日期:** {email['date']}
**邮箱:** {email['mailbox']}
**状态:** {'已读' if email['is_read'] else '未读'}{', ⭐已标记' if email['is_flagged'] else ''}

---

{body}

---
*来自 macOS Mail.app · ID: {email['id']}*
"""
    return memory

# ─── CLI Interface ────────────────────────────────────────────────────────────

def cmd_fetch(args):
    """Fetch recent emails and optionally feed to memory tree"""
    emails = get_recent_emails(args.mailbox, args.limit, args.max_age)
    
    if not emails:
        print(f"No emails found in {args.mailbox}")
        return
    
    print(f"📬 Fetched {len(emails)} emails from {args.mailbox}:\n")
    
    for email in emails:
        read_marker = '✓' if email['is_read'] else '○'
        flagged_marker = '⭐' if email['is_flagged'] else ' '
        print(f"  [{read_marker}{flagged_marker}] {email['date'][:10]} | {email['subject'][:50]}")
        print(f"         From: {email['sender'][:40]}")
        print()
    
    if args.to_memory:
        try:
            import sys
            from pathlib import Path
            memory_tree_py = Path(__file__).parent.parent / "memory_tree" / "memory_tree.py"
            sys.path.insert(0, str(memory_tree_py.parent))
            
            for email in emails:
                memory = email_to_memory(email)
                # Use subprocess to add to memory tree
                import subprocess
                result = subprocess.run(
                    ['python3', str(memory_tree_py), 'add',
                     '--content', memory,
                     '--topic', f"mail:{args.mailbox}"],
                    capture_output=True,
                    timeout=10
                )
        except Exception as e:
            print(f"⚠️  Failed to save to memory tree: {e}")

def cmd_search(args):
    """Search emails by keyword"""
    print(f"🔍 Searching for: {args.keyword}\n")
    
    emails = search_emails(args.keyword, args.mailbox, args.limit)
    
    if not emails:
        print("No matching emails found.")
        return
    
    print(f"Found {len(emails)} results:\n")
    
    for email in emails:
        read_marker = '✓' if email['is_read'] else '○'
        print(f"  [{read_marker}] {email['date'][:10]} | {email['subject']}")
        print(f"         From: {email['sender'][:50]}")
        print(f"         {email['body'][:80]}...")
        print()

def cmd_inbox(args):
    """Get inbox emails (shortcut)"""
    args.mailbox = "INBOX"
    args.to_memory = False
    cmd_fetch(args)

def cmd_status(args):
    """Show mailbox status"""
    try:
        mailboxes = get_mailboxes()
        print(f"📬 Mailboxes in Mail.app ({len(mailboxes)} total):\n")
        
        for mb in mailboxes[:20]:  # Show first 20
            print(f"  • {mb}")
        
        if len(mailboxes) > 20:
            print(f"  ... and {len(mailboxes) - 20} more")
        
        # Get unread count for INBOX
        try:
            script = '''
            tell application "Mail"
                set unreadCount to unread count of inbox
                return unreadCount
            end tell
            '''
            result = run_applescript(script)
            unread = int(result.strip())
            print(f"\n📭 Unread in INBOX: {unread}")
        except:
            pass
        
    except Exception as e:
        print(f"Error: {e}")

def cmd_dump(args):
    """Dump email details to file"""
    emails = get_recent_emails(args.mailbox, args.limit)
    
    output_file = args.output or f"/tmp/mail_dump_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(emails, f, ensure_ascii=False, indent=2)
    
    print(f"Exported {len(emails)} emails to: {output_file}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='macOS Mail Adapter — Read Mail.app without OAuth')
    subparsers = parser.add_subparsers(dest='command')
    
    fetch_parser = subparsers.add_parser('fetch', help='Fetch recent emails')
    fetch_parser.add_argument('--mailbox', '-m', default='INBOX', help='Mailbox name')
    fetch_parser.add_argument('--limit', '-l', type=int, default=20, help='Max emails')
    fetch_parser.add_argument('--max-age', type=int, default=MAX_EMAIL_AGE_DAYS, help='Max age in days')
    fetch_parser.add_argument('--to-memory', action='store_true', help='Save to memory tree')
    
    search_parser = subparsers.add_parser('search', help='Search emails by keyword')
    search_parser.add_argument('keyword', help='Search keyword')
    search_parser.add_argument('--mailbox', '-m', default='INBOX', help='Mailbox to search')
    search_parser.add_argument('--limit', '-l', type=int, default=20, help='Max results')
    
    inbox_parser = subparsers.add_parser('inbox', help='Get inbox emails (shortcut)')
    inbox_parser.add_argument('--limit', '-l', type=int, default=20, help='Max emails')
    
    subparsers.add_parser('status', help='Show mailbox status')
    
    dump_parser = subparsers.add_parser('dump', help='Dump emails to JSON file')
    dump_parser.add_argument('--mailbox', '-m', default='INBOX', help='Mailbox name')
    dump_parser.add_argument('--limit', '-l', type=int, default=50, help='Max emails')
    dump_parser.add_argument('--output', '-o', help='Output file path')
    
    args = parser.parse_args()
    
    if args.command == 'fetch':
        cmd_fetch(args)
    elif args.command == 'search':
        cmd_search(args)
    elif args.command == 'inbox':
        cmd_inbox(args)
    elif args.command == 'status':
        cmd_status(args)
    elif args.command == 'dump':
        cmd_dump(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()

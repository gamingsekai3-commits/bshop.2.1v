"""Rebuilds locale/mn/LC_MESSAGES/django.po + django.mo.

Django ships a Mongolian translation of the admin, but a few strings added in
newer Django versions (the "Run" button, the delete-confirmation sentences,
password-based-authentication wording ...) are still missing from it, so they
showed up in English on the Mongolian admin. This file fills those gaps.

settings.LOCALE_PATHS points at ./locale, which Django checks BEFORE its own
catalogs, so only the strings listed here are overridden.

No GNU gettext install is needed: the .mo is written with the pure-python
`polib` package.   Usage (only when you edit the table below):

    pip install polib
    python scripts/build_mn_overrides.py

The generated django.po / django.mo are committed, so a normal deployment
does not have to run this at all.
"""
from pathlib import Path

import polib

OUT = Path(__file__).resolve().parent.parent / 'locale' / 'mn' / 'LC_MESSAGES'

# msgid -> msgstr   (plural entries: msgid -> (msgid_plural, [form0, form1]))
SINGULAR = {
    # ---- django.contrib.admin ----
    'The app "%s" could not be found.': 'Апп "%s" олдсонгүй.',
    ', ': ', ',
    'Run': 'Гүйцэтгэх',
    'Model name': 'Моделийн нэр',
    'Add link': 'Нэмэх холбоос',
    'Change or view list link': 'Жагсаалт засах / харах холбоос',
    'After you’ve created a user, you’ll be able to edit more user options.':
        'Хэрэглэгчийг үүсгэсний дараа нэмэлт тохиргоог засах боломжтой болно.',
    'Error:': 'Алдаа:',
    'This action will <strong>enable</strong> password-based authentication for this user.':
        'Энэ үйлдэл нь хэрэглэгчид нууц үгээр нэвтрэх боломжийг <strong>идэвхжүүлнэ</strong>.',
    'Disable password-based authentication': 'Нууц үгээр нэвтрэхийг идэвхгүй болгох',
    'Enable password-based authentication': 'Нууц үгээр нэвтрэхийг идэвхжүүлэх',
    'Filter by %(field_name)s': '%(field_name)s-аар шүүх',
    "Deleting the %(object_name)s “%(escaped_object)s” would result in deleting related objects, but your account doesn't have permission to delete the following types of objects:":
        '“%(escaped_object)s” (%(object_name)s)-ийг устгавал холбогдох өгөгдөл мөн устах боловч таны эрх дараах төрлийн өгөгдлийг устгахад хүрэлцэхгүй байна:',
    'Deleting the %(object_name)s “%(escaped_object)s” would require deleting the following protected related objects:':
        '“%(escaped_object)s” (%(object_name)s)-ийг устгахын тулд дараах хамгаалагдсан холбогдох өгөгдлийг мөн устгах шаардлагатай:',
    'Are you sure you want to delete the %(object_name)s “%(escaped_object)s”? All of the following related items will be deleted:':
        '“%(escaped_object)s” (%(object_name)s)-ийг устгахдаа итгэлтэй байна уу? Дараах холбогдох өгөгдлүүд мөн устна:',
    "Deleting the selected %(objects_name)s would result in deleting related objects, but your account doesn't have permission to delete the following types of objects:":
        'Сонгосон %(objects_name)s-ийг устгавал холбогдох өгөгдөл мөн устах боловч таны эрх дараах төрлийн өгөгдлийг устгахад хүрэлцэхгүй байна:',
    'Deleting the selected %(objects_name)s would require deleting the following protected related objects:':
        'Сонгосон %(objects_name)s-ийг устгахын тулд дараах хамгаалагдсан холбогдох өгөгдлийг мөн устгах шаардлагатай:',
    'Are you sure you want to delete the selected %(objects_name)s? All of the following objects and their related items will be deleted:':
        'Сонгосон %(objects_name)s-ийг устгахдаа итгэлтэй байна уу? Дараах өгөгдлүүд болон тэдгээртэй холбоотой бүх зүйл устна:',
    'Forgotten your login credentials?': 'Нэвтрэх мэдээллээ мартсан уу?',
    'Pagination %(name)s entries': '%(name)s бичлэгийн хуудаслалт',
    'Pagination %(name)s': '%(name)s хуудаслалт',
    'Search %(name)s': '%(name)s хайх',
    'Logout': 'Гарах',
    'In case you’ve forgotten, you are:': 'Хэрэв мартсан бол, таны нэр:',
    # ---- django.contrib.auth ----
    'Conflicting form data submitted. Please try again.': 'Маягтын өгөгдөл зөрчилдсөн байна. Дахин оролдоно уу.',
    'Password-based authentication was disabled.': 'Нууц үгээр нэвтрэх идэвхгүй боллоо.',
    'Set password: %s': 'Нууц үг тохируулах: %s',
    'Reset password': 'Нууц үг сэргээх',
    'Set password': 'Нууц үг тохируулах',
    'The two password fields didn’t match.': 'Хоёр нууц үг таарахгүй байна.',
    'Whether the user will be able to authenticate using a password or not. If disabled, they may still be able to authenticate using other backends, such as Single Sign-On or LDAP.':
        'Хэрэглэгч нууц үгээр нэвтрэх эсэх. Идэвхгүй болговол Single Sign-On, LDAP зэрэг өөр аргаар нэвтэрч болно.',
    'Password-based authentication': 'Нууц үгээр нэвтрэх',
    'Enabled': 'Идэвхтэй',
    'Disabled': 'Идэвхгүй',
    'Raw passwords are not stored, so there is no way to see the user’s password.':
        'Нууц үгийг шифрлэгдсэн хэлбэрээр хадгалдаг тул хэрэглэгчийн нууц үгийг харах боломжгүй.',
    'Enable password-based authentication for this user by setting a password.':
        'Нууц үг тохируулснаар энэ хэрэглэгчид нууц үгээр нэвтрэх боломжийг идэвхжүүлнэ.',
    'block size': 'блокийн хэмжээ',
    'Your password can’t be too similar to your other personal information.':
        'Нууц үг таны бусад хувийн мэдээлэлтэй хэт төстэй байж болохгүй.',
    'Your password can’t be a commonly used password.': 'Нууц үг түгээмэл хэрэглэгддэг нууц үг байж болохгүй.',
    'Your password can’t be entirely numeric.': 'Нууц үг зөвхөн тооноос тогтож болохгүй.',
    'Enter a valid username. This value may contain only unaccented lowercase a-z and uppercase A-Z letters, numbers, and @/./+/-/_ characters.':
        'Зөв нэвтрэх нэр оруулна уу. Зөвхөн латин үсэг (a-z, A-Z), тоо болон @/./+/-/_ тэмдэгт ашиглана.',
    'Enter a valid username. This value may contain only letters, numbers, and @/./+/-/_ characters.':
        'Зөв нэвтрэх нэр оруулна уу. Зөвхөн үсэг, тоо болон @/./+/-/_ тэмдэгт ашиглана.',
}

PLURAL = {
    '…and %(count)d more object.': ('…and %(count)d more objects.',
                                     ['…мөн %(count)d өгөгдөл байна.', '…мөн %(count)d өгөгдөл байна.']),
    'This password is too short. It must contain at least %d character.':
        ('This password is too short. It must contain at least %d characters.',
         ['Нууц үг хэт богино байна. Хамгийн багадаа %d тэмдэгт байх ёстой.',
          'Нууц үг хэт богино байна. Хамгийн багадаа %d тэмдэгт байх ёстой.']),
}


def main():
    po = polib.POFile()
    po.metadata = {
        'Project-Id-Version': 'bshop',
        'Language': 'mn',
        'MIME-Version': '1.0',
        'Content-Type': 'text/plain; charset=UTF-8',
        'Content-Transfer-Encoding': '8bit',
        'Plural-Forms': 'nplurals=2; plural=(n != 1);',
    }
    for msgid, msgstr in SINGULAR.items():
        po.append(polib.POEntry(msgid=msgid, msgstr=msgstr))
    for msgid, (plural, forms) in PLURAL.items():
        po.append(polib.POEntry(msgid=msgid, msgid_plural=plural,
                                msgstr_plural={i: f for i, f in enumerate(forms)}))
    OUT.mkdir(parents=True, exist_ok=True)
    po.save(str(OUT / 'django.po'))
    po.save_as_mofile(str(OUT / 'django.mo'))
    print(f'{len(po)} entries -> {OUT}')


if __name__ == '__main__':
    main()

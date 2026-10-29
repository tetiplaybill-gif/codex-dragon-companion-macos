"""Login Keychain secrets for macOS through Security.framework; no extra dependency."""
import ctypes
from pathlib import Path

SERVICE='BailongEnhanced'
NOT_FOUND=-25300 # errSecItemNotFound
_lib=None

def _api():
    global _lib
    if _lib is None:
        cf=ctypes.CDLL('/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation')
        sec=ctypes.CDLL('/System/Library/Frameworks/Security.framework/Security')
        P=ctypes.c_void_p;S=ctypes.c_int32
        for name,res,args in [('CFStringCreateWithCString',P,[P,ctypes.c_char_p,ctypes.c_uint32]),('CFDataCreate',P,[P,ctypes.c_char_p,ctypes.c_long]),
                ('CFDictionaryCreate',P,[P,ctypes.POINTER(P),ctypes.POINTER(P),ctypes.c_long,P,P]),('CFDataGetLength',ctypes.c_long,[P]),
                ('CFDataGetBytePtr',P,[P]),('CFRelease',None,[P]),('CFArrayGetCount',ctypes.c_long,[P]),('CFArrayGetValueAtIndex',P,[P,ctypes.c_long]),
                ('CFDictionaryGetValue',P,[P,P]),('CFStringGetCString',ctypes.c_bool,[P,ctypes.c_char_p,ctypes.c_long,ctypes.c_uint32])]:
            f=getattr(cf,name);f.restype=res;f.argtypes=args
        for name,args in [('SecItemAdd',[P,P]),('SecItemCopyMatching',[P,ctypes.POINTER(P)]),('SecItemUpdate',[P,P]),('SecItemDelete',[P])]:
            f=getattr(sec,name);f.restype=S;f.argtypes=args
        k=lambda lib,name:P.in_dll(lib,name).value
        _lib=dict(cf=cf,sec=sec,keys=ctypes.addressof(P.in_dll(cf,'kCFTypeDictionaryKeyCallBacks')),values=ctypes.addressof(P.in_dll(cf,'kCFTypeDictionaryValueCallBacks')),
            true=k(cf,'kCFBooleanTrue'),**{n:k(sec,n) for n in ('kSecClass','kSecClassGenericPassword','kSecAttrService','kSecAttrAccount','kSecValueData','kSecReturnData','kSecReturnAttributes','kSecMatchLimit','kSecMatchLimitOne','kSecMatchLimitAll')})
    return _lib

class KeychainStore:
    """Same read/get/put contract as the Windows DPAPI SecretStore; the path is kept only for callers."""
    def __init__(self,path=None,service=SERVICE):self.path=Path(path) if path else None;self.service=service
    def _call(self,function,pairs,*extra):
        a=_api();cf=a['cf'];owned=[]
        def ref(value):
            if isinstance(value,str):value=cf.CFStringCreateWithCString(None,value.encode('utf-8'),0x08000100)
            elif isinstance(value,bytes):value=cf.CFDataCreate(None,value,len(value))
            else:return value
            if not value:raise OSError('钥匙串参数创建失败')
            owned.append(value);return value
        def dictionary(items):
            keys=(ctypes.c_void_p*len(items))(*[a[k] for k,_ in items]);vals=(ctypes.c_void_p*len(items))(*[ref(v) for _,v in items])
            d=cf.CFDictionaryCreate(None,keys,vals,len(items),a['keys'],a['values'])
            if not d:raise OSError('钥匙串参数创建失败')
            owned.append(d);return d
        try:return function(dictionary(pairs),*[dictionary(e) if isinstance(e,list) else e for e in extra])
        finally:
            for value in owned:cf.CFRelease(value)
    def _query(self,name):a=_api();return [('kSecClass',a['kSecClassGenericPassword']),('kSecAttrService',self.service),('kSecAttrAccount',str(name))]
    def get(self,name):
        a=_api();result=ctypes.c_void_p()
        status=self._call(a['sec'].SecItemCopyMatching,self._query(name)+[('kSecReturnData',a['true']),('kSecMatchLimit',a['kSecMatchLimitOne'])],ctypes.byref(result))
        if status==NOT_FOUND:return ''
        if status or not result.value:raise OSError('无法读取钥匙串中的密钥（%d）'%status)
        try:return ctypes.string_at(a['cf'].CFDataGetBytePtr(result),a['cf'].CFDataGetLength(result)).decode('utf-8')
        except UnicodeError:raise OSError('无法读取钥匙串中的密钥') from None
        finally:a['cf'].CFRelease(result)
    def put(self,name,value):
        sec=_api()['sec']
        if not value:
            status=self._call(sec.SecItemDelete,self._query(name))
            if status not in (0,NOT_FOUND):raise OSError('无法删除钥匙串中的密钥（%d）'%status)
            return
        data=value.encode('utf-8');status=self._call(sec.SecItemUpdate,self._query(name),[('kSecValueData',data)])
        if status==NOT_FOUND:status=self._call(sec.SecItemAdd,self._query(name)+[('kSecValueData',data)],None)
        if status:raise OSError('无法写入钥匙串（%d）'%status)
    def read(self):
        """Names of stored items, mapped to a non-empty placeholder.

        Only attributes are queried, so listing never prompts for Keychain
        access and never returns secret values.
        """
        a=_api();cf=a['cf'];result=ctypes.c_void_p()
        status=self._call(a['sec'].SecItemCopyMatching,[('kSecClass',a['kSecClassGenericPassword']),('kSecAttrService',self.service),
            ('kSecReturnAttributes',a['true']),('kSecMatchLimit',a['kSecMatchLimitAll'])],ctypes.byref(result))
        if status==NOT_FOUND:return {}
        if status or not result.value:raise OSError('无法读取钥匙串中的密钥列表（%d）'%status)
        names={};buffer=ctypes.create_string_buffer(1024)
        try:
            for index in range(cf.CFArrayGetCount(result)):
                account=cf.CFDictionaryGetValue(cf.CFArrayGetValueAtIndex(result,index),a['kSecAttrAccount'])
                if account and cf.CFStringGetCString(account,buffer,len(buffer),0x08000100):
                    names[buffer.value.decode('utf-8')]='keychain'
        finally:cf.CFRelease(result)
        return names
    def remove(self,names):
        """Delete items one by one; there is no shared document to rewrite."""
        failed=[]
        for name in names:
            try:self.put(name,'')
            except OSError:failed.append(name)
        if failed:raise OSError('无法删除钥匙串中的 %d 个密钥'%len(failed))

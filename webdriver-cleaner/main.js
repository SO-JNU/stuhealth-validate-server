Reflect.defineProperty(window.navigator.wrappedJSObject, 'webdriver', {
    get: exportFunction(() => undefined, window.wrappedJSObject),
});
console.log('navigator.webdriver cleaned:', window.navigator.wrappedJSObject.webdriver);
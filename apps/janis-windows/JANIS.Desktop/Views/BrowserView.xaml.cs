using System.Windows;
using System.Windows.Controls;
using Microsoft.Web.WebView2.Core;

namespace JANIS.Desktop.Views;

public partial class BrowserView : UserControl
{
    public BrowserView()
    {
        InitializeComponent();
        Loaded += OnLoaded;
    }

    async void OnLoaded(object sender, RoutedEventArgs e)
    {
        try
        {
            await Browser.EnsureCoreWebView2Async();
            Go_Click(this, new RoutedEventArgs());
        }
        catch (Exception ex)
        {
            UrlBox.Text = "WebView2: " + ex.Message;
        }
    }

    void Go_Click(object sender, RoutedEventArgs e)
    {
        var url = UrlBox.Text.Trim();
        if (!url.StartsWith("http", StringComparison.OrdinalIgnoreCase))
            url = "https://" + url;
        if (Browser.CoreWebView2 != null)
            Browser.CoreWebView2.Navigate(url);
    }
}
